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
    ChatMemberHandler,
    filters,
)

# === Версія коду ===
__version__ = "5"

# --- ЛОГІНГ ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ШЛЯХИ і ЗАВАНТАЖЕННЯ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_PATH = os.path.join(BASE_DIR, "questions.yaml")
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# --- НАЛАШТУВАННЯ з ENV ---
DELETE_MESSAGES_DELAY = int(os.getenv("DELETE_MESSAGES_DELAY", 10))
QUESTION_MESSAGES_DELAY = int(os.getenv("QUESTION_MESSAGES_DELAY", 60))
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "")

# Завантаження питань
with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
    QUESTIONS = yaml.safe_load(f)

# Завантаження приватних кнопок
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
PRIVATE_BUTTONS = CONFIG.get("private_buttons", [])

# --- Дозволені групи ---
if CHAT_IDS:
    ALLOWED_CHAT_IDS = [int(x) for x in CHAT_IDS.split(",") if x.strip()]
else:
    ALLOWED_CHAT_IDS = []
logger.info(f"Allowed chat IDs: {ALLOWED_CHAT_IDS}")

# --- ПРАВА ---
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

# Сесії з питаннями
user_questions = {}  # user_id -> {answer, message_id, timer}


async def delete_message_later(bot, chat_id, msg_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, msg_id)
        logger.info(f"[CLEANUP] Видалено повідомлення {msg_id} в чаті {chat_id}")
    except Exception as e:
        logger.warning(f"[CLEANUP ERROR] Не вдалося видалити повідомлення {msg_id}: {e}")


async def check_allowed_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if chat.type != "private" and chat.id not in ALLOWED_CHAT_IDS:
        try:
            await context.bot.send_message(chat.id, "⛔ Бот працює тільки в авторизованих групах.")
        except:
            pass
        await context.bot.leave_chat(chat.id)
        return False
    return True


# --- ГРУПА 0: видаляємо системні меседжі про join/leave
async def delete_service_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    try:
        await context.bot.delete_message(msg.chat.id, msg.message_id)
    except Exception as e:
        logger.debug(f"Cannot delete service msg {msg.message_id}: {e}")


# --- ГРУПА 1: класичне приєднання “натисканням”
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("new_member handler invoked")
    if not await check_allowed_chat(update, context):
        logger.info("new_member aborted: unauthorized chat")
        return

    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        logger.info(f"Restricting new member {member.id} ({member.full_name}) in chat {chat_id}")
        await context.bot.restrict_chat_member(chat_id, member.id, RESTRICTED)

        # Відправляємо питання
        q = random.choice(QUESTIONS)
        correct = q["answer"].strip().lower()
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(opt, callback_data=f"{member.id}:{opt.strip().lower()}")]
                for opt in q.get("options", [])
            ]
        )
        sent = await context.bot.send_message(
            chat_id,
            f"{member.full_name}, щоб почати — оберіть правильну відповідь:\n❓ {q['question']}",
            reply_markup=kb,
        )

        task = asyncio.create_task(delete_message_later(context.bot, chat_id, sent.message_id, QUESTION_MESSAGES_DELAY))
        user_questions[member.id] = {
            "answer": correct,
            "message_id": sent.message_id,
            "timer": task,
        }


# --- ГРУПА 1: приєднання через API (joinChat, invite link) ---
async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("chat_member handler invoked")
    cm = update.chat_member
    chat = update.effective_chat
    old, new = cm.old_chat_member.status, cm.new_chat_member.status

    if old in ("left", "kicked") and new == "member":
        if not await check_allowed_chat(update, context):
            logger.info("chat_member aborted: unauthorized chat")
            return

        user = cm.new_chat_member.user
        logger.info(f"Restricting new member {user.id} in chat {chat.id}")
        await context.bot.restrict_chat_member(chat.id, user.id, RESTRICTED)

        # Повторюємо питання
        q = random.choice(QUESTIONS)
        correct = q["answer"].strip().lower()
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(opt, callback_data=f"{user.id}:{opt.strip().lower()}")]
                for opt in q.get("options", [])
            ]
        )
        sent = await context.bot.send_message(
            chat.id,
            f"{user.full_name}, щоб почати — оберіть правильну відповідь:\n❓ {q['question']}",
            reply_markup=kb,
        )

        task = asyncio.create_task(delete_message_later(context.bot, chat.id, sent.message_id, QUESTION_MESSAGES_DELAY))
        user_questions[user.id] = {
            "answer": correct,
            "message_id": sent.message_id,
            "timer": task,
        }


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


# --- Приватні кнопки і /start ---
async def handle_private_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"handle_private_buttons with text '{text}'")
    for btn in PRIVATE_BUTTONS:
        if update.message.text == btn["label"]:
            await update.message.reply_text(btn["response"])
            return


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        labels = [b["label"] for b in PRIVATE_BUTTONS]
        keyboard = [labels[i : i + 2] for i in range(0, len(labels), 2)]
        await update.message.reply_text(
            "Я — JAAM-бот.\n"
            "Вітаю Вас в проекті JAAM.\n\n"
            "Я допоможу Вам бути в курсі всіх новин або отримати допомогу.\n\n"
            "Виберіть кнопку нижче, щоб продовжити.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
    else:
        if await check_allowed_chat(update, context):
            await update.message.reply_text("Привіт! Напишіть мені в лічку.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не заданий")
    app = Application.builder().token(BOT_TOKEN).build()

    # Група 0 — видалення сервісних повідомлень про приєднання/вихід
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
            delete_service_message,
        ),
        group=0,
    )

    # Група 1 — логіка запитань
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member), group=1)
    app.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER), group=1)

    # Інші хендлери
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.Regex(rf"^({'|'.join(map(re.escape, [b['label'] for b in PRIVATE_BUTTONS]))})$"),
            handle_private_buttons,
        )
    )

    logger.info("🚀 Бот запущено")
    app.run_polling()


if __name__ == "__main__":
    main()
