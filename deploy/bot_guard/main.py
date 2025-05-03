import os
import random
import logging
import asyncio
import yaml
import re
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

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
__version__ = "20"

# --- ШЛЯХИ і ЗАВАНТАЖЕННЯ ---
BASE_PATH = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.join(BASE_PATH, "questions.yaml")
CONFIG_PATH = os.path.join(BASE_PATH, "config.yaml")
FONT_PATH = os.path.join(BASE_PATH, "ArialUnicodeBold.ttf")
DEBUG_LEVEL = os.environ.get("LOGGING") or "DEBUG"


# --- ЛОГИ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,     # root-logger: лише WARNING+ для всіх пакетів
)
logger = logging.getLogger(__name__)
logger.setLevel(DEBUG_LEVEL)  # цей файл: INFO

logger.debug(f"QUESTIONS_PATH: {QUESTIONS_PATH}")
logger.debug(f"CONFIG_PATH: {CONFIG_PATH}")


# --- НАЛАШТУВАННЯ ---
DELETE_MESSAGES_DELAY = int(os.getenv("DELETE_MESSAGES_DELAY", 2))
QUESTION_MESSAGES_DELAY = int(os.getenv("QUESTION_MESSAGES_DELAY", 30))
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "")
USE_CAPTCHA = os.getenv("USE_CAPTCHA", "false").lower() in ("true", "1", "yes")

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


# --- УТИЛІТИ ---
async def delete_message_later(bot, chat_id, msg_id, delay):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, msg_id)
        logger.info(f"[CLEANUP] Видалено повідомлення {msg_id} в чаті {chat_id}")
    except Exception as e:
        logger.warning(f"[CLEANUP ERROR] Не вдалося видалити повідомлення {msg_id}: {e}")

async def handle_timeout(bot, chat_id, user_id, msg_id, delay):
    await asyncio.sleep(delay)
    # Видаляємо повідомлення з питання
    try:
        await bot.delete_message(chat_id, msg_id)
        logger.info(f"[TIMEOUT] Видалено питання {msg_id} в чаті {chat_id}")
    except Exception as e:
        logger.warning(f"[TIMEOUT ERROR] Не вдалося видалити питання {msg_id}: {e}")
    # Видаляємо користувача з чату
    try:
        await bot.ban_chat_member(chat_id, user_id)
        logger.info(f"[TIMEOUT] Видалений користувач {user_id} з чату {chat_id} через timeout відповіді")
    except Exception as e:
        logger.warning(f"[TIMEOUT ERROR] Не вдалося видалити користувача {user_id}: {e}")

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


# --- CAPTCHA ---
alphabet_pool = list("абвгдежзийклмнопрстуфхцчшщьюяєії0123456789")


def generate_captcha():
    text = "".join(random.choice(alphabet_pool) for _ in range(4))
    options = [text] + ["".join(random.choice(alphabet_pool) for _ in range(4)) for _ in range(5)]
    random.shuffle(options)

    width, height = 100, 50
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    font_path = FONT_PATH
    # Бінарний пошук максимально великого шрифту
    if font_path:
        low, high, best = 8, height, 8
        ratio = 0.9
        while low <= high:
            mid = (low + high) // 2
            font = ImageFont.truetype(font_path, mid)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= width * ratio and th <= height * ratio:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        font = ImageFont.truetype(font_path, best)
        logger.info(f"generate_captcha: using font {font_path} size {best}")
    else:
        font = ImageFont.load_default()
        logger.info("generate_captcha: using default font")

    # Центрування тексту
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill="black")

    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf, text, options


# --- Сесії ---
user_questions = {}


# --- СТАРІ ХЕНДЛЕРИ ---
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_allowed_chat(update, context):
        return
    chat_id = update.effective_chat.id
    for m in update.message.new_chat_members:
        logger.info(f"[NEW MEMBER] {m.full_name} в чаті {chat_id}")
        if m.id in user_questions:
            continue
        await context.bot.restrict_chat_member(chat_id, m.id, RESTRICTED)
        q = random.choice(QUESTIONS)
        ans = q["answer"].strip().lower()
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(opt, callback_data=f"{m.id}:{opt.strip().lower()}")] for opt in q.get("options", [])]
        )
        msg = await context.bot.send_message(
            chat_id,
            f"{m.full_name}, відповідайте:\n❓ {q['question']}",
            reply_markup=kb,
        )
        user_questions[m.id] = {
            "answer": ans,
            "message_id": msg.message_id,
            "timer": asyncio.create_task(
                handle_timeout(context.bot, chat_id, m.id, msg.message_id, QUESTION_MESSAGES_DELAY)
            ),
        }


async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member
    u = cm.new_chat_member.user
    if (
        cm.old_chat_member.status in (ChatMember.LEFT, ChatMember.RESTRICTED)
        and cm.new_chat_member.status == ChatMember.MEMBER
    ):
        logger.info(f"[CHAT MEMBER] {u.full_name} в чаті {chat_id}")
        if u.id in user_questions:
            return
        chat_id = update.effective_chat.id
        await context.bot.restrict_chat_member(chat_id, u.id, RESTRICTED)
        q = random.choice(QUESTIONS)
        ans = q["answer"].strip().lower()
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(opt, callback_data=f"{u.id}:{opt.strip().lower()}")] for opt in q.get("options", [])]
        )
        msg = await context.bot.send_message(
            chat_id,
            f"{u.full_name}, відповідайте:\n❓ {q['question']}",
            reply_markup=kb,
        )
        user_questions[u.id] = {
            "answer": ans,
            "message_id": msg.message_id,
            "timer": asyncio.create_task(
                handle_timeout(context.bot, chat_id, u.id, msg.message_id, QUESTION_MESSAGES_DELAY)
            ),
        }


# --- НОВІ CAPTCHA ХЕНДЛЕРИ ---
async def new_member_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_allowed_chat(update, context):
        return
    chat_id = update.effective_chat.id
    for m in update.message.new_chat_members:
        logger.info(f"[NEW MEMBER CAPTCHA] {m.full_name} в чаті {chat_id}")
        if m.id in user_questions:
            continue
        await context.bot.restrict_chat_member(chat_id, m.id, RESTRICTED)
        buf, ans, opts = generate_captcha()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(o, callback_data=f"{m.id}:{o}")] for o in opts])
        msg = await context.bot.send_photo(
            chat_id,
            photo=buf,
            caption=f"{m.full_name}, введіть текст капчі:",
            reply_markup=kb,
        )
        user_questions[m.id] = {
            "answer": ans,
            "message_id": msg.message_id,
            "timer": asyncio.create_task(
                handle_timeout(context.bot, chat_id, m.id, msg.message_id, QUESTION_MESSAGES_DELAY)
            ),
        }


async def on_chat_member_update_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member
    u = cm.new_chat_member.user
    if (
        cm.old_chat_member.status in (ChatMember.LEFT, ChatMember.RESTRICTED)
        and cm.new_chat_member.status == ChatMember.MEMBER
    ):
        logger.info(f"[CHAT MEMBER CAPTCHA] {u.full_name} в чаті {chat_id}")
        if u.id in user_questions:
            return
        chat_id = update.effective_chat.id
        await context.bot.restrict_chat_member(chat_id, u.id, RESTRICTED)
        buf, ans, opts = generate_captcha()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(o, callback_data=f"{u.id}:{o}")] for o in opts])
        msg = await context.bot.send_photo(
            chat_id,
            photo=buf,
            caption=f"{u.full_name}, введіть текст капчі:",
            reply_markup=kb,
        )
        user_questions[u.id] = {
            "answer": ans,
            "message_id": msg.message_id,
            "timer": asyncio.create_task(
                handle_timeout(context.bot, chat_id, u.id, msg.message_id, QUESTION_MESSAGES_DELAY)
            ),
        }


# --- ОБРОБКА ВІДПОВІДІ ---
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat = q.message.chat
    user = q.from_user
    if chat.type != "private" and chat.id not in ALLOWED_CHAT_IDS:
        return
    uid, ans = q.data.split(":", 1)
    if user.id != int(uid):
        return await q.answer("⛔ Не ваше питання.", show_alert=True)
    entry = user_questions.get(user.id)
    if not entry:
        return await q.answer("⚠ Сеанс недійсний.", show_alert=True)
    if ans == entry["answer"]:
        await context.bot.restrict_chat_member(chat.id, user.id, UNRESTRICTED)
        res = "✅ Правильно! Доступ відкрито."
    else:
        res = "❌ Неправильно. Спробуйте пізніше."
    try:
        if q.message.photo:
            await q.edit_message_caption(res)
        else:
            await q.edit_message_text(res)
    except:
        pass
    entry["timer"].cancel()
    asyncio.create_task(delete_message_later(context.bot, chat.id, entry["message_id"], DELETE_MESSAGES_DELAY))
    del user_questions[user.id]


# --- ПРИВАТНІ КНОПКИ ---
async def handle_private_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    for btn in PRIVATE_BUTTONS:
        if text == btn["label"]:
            return await update.message.reply_text(btn["response"])


# --- /start ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        labels = [b["label"] for b in PRIVATE_BUTTONS]
        kb = [labels[i : i + 2] for i in range(0, len(labels), 2)]
        await update.message.reply_text(
            "Я — JAAM-бот.\nВиберіть кнопку:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
    else:
        if await check_allowed_chat(update, context):
            await update.message.reply_text("Привіт! Пишіть в лічку.")


# --- MAIN ---
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не заданий")
    app = Application.builder().token(BOT_TOKEN).build()
    labels_pattern = "|".join(re.escape(b["label"]) for b in PRIVATE_BUTTONS)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.Regex(rf"^({labels_pattern})$"), handle_private_buttons)
    )
    if USE_CAPTCHA:
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_captcha))
        app.add_handler(ChatMemberHandler(on_chat_member_update_captcha, ChatMemberHandler.CHAT_MEMBER))
    else:
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
        app.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.run_polling(allowed_updates=["message", "callback_query", "chat_member"])


if __name__ == "__main__":
    main()
