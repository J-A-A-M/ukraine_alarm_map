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
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# === Версія коду ===
__version__ = "5"

# --- ЛОГИ ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ШЛЯХИ і ЗАВАНТАЖЕННЯ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_PATH = os.path.join(BASE_DIR, "questions.yaml")
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

logger.debug(f"BASE_DIR: {BASE_DIR}")
logger.debug(f"QUESTIONS_PATH: {QUESTIONS_PATH}")
logger.debug(f"CONFIG_PATH: {CONFIG_PATH}")

# Завантаження питань з YAML
with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
    QUESTIONS = yaml.safe_load(f)
logger.debug(f"Loaded {len(QUESTIONS)} questions from YAML")

# Завантаження конфігу (тільки кнопки)
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
PRIVATE_BUTTONS = CONFIG.get("private_buttons", [])
logger.debug(f"Private buttons: {PRIVATE_BUTTONS}")

# --- Дозволені групи через ENV ---
env_ids = os.getenv("ALLOWED_CHAT_IDS", "")
if env_ids:
    ALLOWED_CHAT_IDS = [int(x) for x in env_ids.split(",") if x.strip()]
else:
    ALLOWED_CHAT_IDS = []
logger.debug(f"Allowed chat IDs (from ENV): {ALLOWED_CHAT_IDS}")

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

# --- Стан сеансів ---
user_questions = {}  # user_id: {"answer": str, "message_id": int, "timer": asyncio.Task}
logger.debug("Initialized user_questions store")


async def delete_message_later(bot, chat_id, msg_id, delay):
    logger.debug(f"Scheduling delete for msg {msg_id} in chat {chat_id} after {delay}s")
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
        except Exception:
            logger.exception("Failed to send unauthorized message")
        await context.bot.leave_chat(chat.id)
        return False
    return True


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

        task = asyncio.create_task(delete_message_later(context.bot, chat_id, sent.message_id, 60))
        user_questions[member.id] = {"answer": correct, "message_id": sent.message_id, "timer": task}
        logger.debug(f"Stored session for user {member.id}")


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    user = query.from_user
    logger.info(f"handle_answer invoked by user {user.id} in chat {chat.id}")

    if chat.type != "private" and chat.id not in ALLOWED_CHAT_IDS:
        logger.warning(f"Ignoring answer in unauthorized chat {chat.id}")
        return

    user_id_str, answer = query.data.split(":", 1)
    expected = int(user_id_str)
    if user.id != expected:
        logger.warning(f"User {user.id} attempted to answer question of {expected}")
        await query.answer("⛔ Це не ваше питання.", show_alert=True)
        return

    entry = user_questions.get(user.id)
    if not entry:
        logger.warning(f"No session entry for user {user.id}")
        await query.answer("⚠ Сеанс недійсний.", show_alert=True)
        return

    correct = entry["answer"]
    msg_id = entry["message_id"]
    logger.debug(f"User answer='{answer}', correct='{correct}'")

    if answer == correct:
        await context.bot.restrict_chat_member(chat.id, user.id, UNRESTRICTED)
        await query.edit_message_text("✅ Правильно! Доступ відкрито.")
        logger.info(f"[ACCESS GRANTED] User {user.id}")
    else:
        await query.edit_message_text("❌ Неправильно. Спробуй пізніше.")
        logger.info(f"[WRONG ANSWER] User {user.id}")

    entry["timer"].cancel()
    asyncio.create_task(delete_message_later(context.bot, chat.id, msg_id, 10))
    del user_questions[user.id]
    logger.debug(f"Session cleared for user {user.id}")


async def handle_private_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"handle_private_buttons with text '{text}'")
    for btn in PRIVATE_BUTTONS:
        if text == btn["label"]:
            await update.message.reply_text(btn["response"])
            logger.debug(f"Replied to private button '{text}'")
            return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    logger.info(f"start_command invoked in chat {chat.id} (type={chat.type})")
    if chat.type == "private":
        labels = [btn["label"] for btn in PRIVATE_BUTTONS]
        keyboard = [labels[i : i + 2] for i in range(0, len(labels), 2)]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            "Вітаю! Я — JAAM-бот.\n"
            "Вітаю тебе в проекті JAAM.\n\n"
            "Я допоможу тобі бути в курсі всіх новин або отримати допомогу.\n\n"
            "Вибери кнопку нижче, щоб продовжити.",
            reply_markup=markup,
        )
        logger.debug("Sent private menu keyboard")
    else:
        if await check_allowed_chat(update, context):
            await update.message.reply_text("Привіт! Додай мене в авторизовану групу.")
            logger.debug("Sent group instruction message")


if __name__ == "__main__":

    def main():
        logger.info("🚀 Запуск бота")
        token = os.getenv("BOT_TOKEN")
        if not token:
            logger.error("BOT_TOKEN не заданий")
            raise RuntimeError("BOT_TOKEN не заданий")
        app = Application.builder().token(token).build()

        allowed = "|".join(map(lambda b: re.escape(b["label"]), PRIVATE_BUTTONS))

        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
        app.add_handler(CallbackQueryHandler(handle_answer))
        app.add_handler(
            MessageHandler(
                filters.ChatType.PRIVATE
                & filters.Regex(rf"^({allowed})$"),
                handle_private_buttons,
            )
        )

        app.run_polling()

    main()
