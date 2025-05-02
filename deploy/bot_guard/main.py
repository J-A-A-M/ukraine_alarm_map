import os
import random
import logging
import asyncio
import yaml
import re

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ChatMember,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

# === Версія коду ===
__version__ = "5"

# --- ЛОГИ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- ШЛЯХИ і ЗАВАНТАЖЕННЯ ---
BASE_PATH = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.join(BASE_PATH, "questions.yaml")
CONFIG_PATH = os.path.join(BASE_PATH, "config.yaml")
logger.debug(f"QUESTIONS_PATH: {QUESTIONS_PATH}")
logger.debug(f"CONFIG_PATH: {CONFIG_PATH}")

# --- НАЛАШТУВАННЯ ---
DELETE_MESSAGES_DELAY = int(os.getenv("DELETE_MESSAGES_DELAY", 10))
QUESTION_MESSAGES_DELAY = int(os.getenv("QUESTION_MESSAGES_DELAY", 60))
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "")

# Завантаження питань з YAML
with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
    QUESTIONS = yaml.safe_load(f)
logger.debug(f"Loaded {len(QUESTIONS)} questions from YAML")

# Завантаження конфігу (тільки кнопки)
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
PRIVATE_BUTTONS = CONFIG.get("private_buttons", [])
logger.debug(f"Loaded {len(PRIVATE_BUTTONS)} private buttons")

if CHAT_IDS:
    ALLOWED_CHAT_IDS = [int(x) for x in CHAT_IDS.split(",") if x.strip()]
else:
    ALLOWED_CHAT_IDS = []
logger.info(f"Allowed chat IDs (from ENV): {ALLOWED_CHAT_IDS}")

# --- ПРАВА ДОСТУПУ ---
RESTRICTED = ChatPermissions(can_send_messages=False)
UNRESTRICTED = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)

# --- УТИЛІТИ ---
async def delete_message_later(bot, chat_id, msg_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, msg_id)
        logger.info(f"[CLEANUP] Видалено повідомлення {msg_id} в чаті {chat_id}")
    except Exception as e:
        logger.warning(f"[CLEANUP ERROR] Не вдалося видалити повідомлення {msg_id}: {e}")

async def check_allowed_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    logger.debug(f"check_allowed_chat: chat_id={chat.id}, type={chat.type}")
    if chat.type != "private" and chat.id not in ALLOWED_CHAT_IDS:
        logger.warning(f"Unauthorized group {chat.id}, leaving.")
        try:
            await context.bot.send_message(chat.id, "⛔ Бот працює лише в авторизованих групах.")
        except:
            pass
        return False
    return True

# --- ХЕНДЛЕР НА НОВЕ ПРИЄДНАННЯ З ПИТАННЯМ ---
user_questions = {}

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("new_member handler invoked")
    if not await check_allowed_chat(update, context):
        logger.info("new_member aborted: unauthorized chat")
        return

    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        logger.info(f"Restricting new member {member.id} ({member.full_name}) in chat {chat_id}")
        await context.bot.restrict_chat_member(chat_id, member.id, RESTRICTED)

        q = random.choice(QUESTIONS)
        correct = q["answer"].strip().lower()
        options = q.get("options", [])
        logger.debug(f"Selected question: {q['question']} with options {options} (answer={correct})")

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(opt, callback_data=f"{member.id}:{opt.strip().lower()}")] for opt in options]
        )
        sent = await context.bot.send_message(
            chat_id,
            f"{member.full_name}, щоб почати спілкування, обери правильну відповідь:\n❓ {q['question']}",
            reply_markup=kb,
        )
        logger.debug(f"Sent question message {sent.message_id} to {member.id}")

        task = asyncio.create_task(
            delete_message_later(context.bot, chat_id, sent.message_id, QUESTION_MESSAGES_DELAY)
        )
        user_questions[member.id] = {"answer": correct, "message_id": sent.message_id, "timer": task}
        logger.debug(f"Stored session for user {member.id}")

# --- ХЕНДЛЕР ДЛЯ ВСІХ СТАТУСІВ УЧАСНИКІВ ---
async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє зміни статусу учасника чату."""
    cmu = update.chat_member
    old_status = cmu.old_chat_member.status
    new_status = cmu.new_chat_member.status

    if old_status in (ChatMember.LEFT, ChatMember.RESTRICTED) and new_status == ChatMember.MEMBER:
        user = cmu.new_chat_member.user
        if cmu.invite_link:
            via = f"через посилання `{cmu.invite_link.invite_link}`"
        else:
            via = "додана адміністратором"
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"👋 Користувач {user.mention_html()} приєднався до чату {via}."
            ),
            parse_mode="HTML",
        )
# --- Обробка відповіді ---
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    user = query.from_user
    logger.info(f"handle_answer invoked by user {user.id} in chat {chat.id}")

    if chat.type != "private" and chat.id not in ALLOWED_CHAT_IDS:
        return

    uid_str, ans = query.data.split(":", 1)
    if user.id != int(uid_str):
        await query.answer("⛔ Це не ваше питання.", show_alert=True)
        return

    entry = user_questions.get(user.id)
    if not entry:
        await query.answer("⚠ Сеанс недійсний.", show_alert=True)
        return

    if ans == entry["answer"]:
        await context.bot.restrict_chat_member(chat.id, user.id, UNRESTRICTED)
        await query.edit_message_text("✅ Правильно! Доступ відкрито.")
    else:
        await query.edit_message_text("❌ Неправильно. Спробуйте пізніше.")

    entry["timer"].cancel()
    asyncio.create_task(delete_message_later(context.bot, chat.id, entry["message_id"], DELETE_MESSAGES_DELAY))
    del user_questions[user.id]

# --- ХЕНДЛЕР ДЛЯ ПРИВАТНИХ КНОПОК ---
async def handle_private_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"handle_private_buttons with text '{text}'")
    for btn in PRIVATE_BUTTONS:
        if text == btn["label"]:
            await update.message.reply_text(btn["response"])
            logger.debug(f"Replied to private button '{text}'")
            return

# --- ХЕНДЛЕР КОМАНДИ /start ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    logger.info(f"start_command invoked in chat {chat.id} (type={chat.type})")
    if chat.type == "private":
        labels = [btn["label"] for btn in PRIVATE_BUTTONS]
        keyboard = [labels[i : i + 2] for i in range(0, len(labels), 2)]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Я — JAAM-бот.\n"
            "Я допоможу Вам бути в курсі всіх новин або отримати допомогу.\n"
            "Виберіть кнопку нижче, щоб продовжити",
            reply_markup=markup,
        )
        logger.debug("Sent private menu keyboard")
    else:
        if await check_allowed_chat(update, context):
            await update.message.reply_text("Привіт! Якщо хочешь зі мною поспілкуватись - пиши в лічку.")
            logger.debug("Sent group instruction message")

if __name__ == "__main__":
    def main():
        logger.info("🚀 Запуск бота")
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN не заданий")
            raise RuntimeError("BOT_TOKEN не заданий")
        app = Application.builder().token(BOT_TOKEN).build()

        allowed = "|".join(map(lambda b: re.escape(b["label"]), PRIVATE_BUTTONS))

        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
        app.add_handler(CallbackQueryHandler(handle_answer))
        app.add_handler(
            MessageHandler(
                filters.ChatType.PRIVATE & filters.Regex(rf"^({allowed})$"),
                handle_private_buttons,
            )
        )
        # Відстежуємо будь-які приєднання до чату
        app.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

        # Запускаємо бот з отриманням оновлень про повідомлення, callback_query та chat_member
        app.run_polling(allowed_updates=["message", "callback_query", "chat_member"])

    main()