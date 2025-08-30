
import os
import re
import json
import asyncio
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions, User
from telegram.constants import ChatType, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from openai import OpenAI

from memory import init_db, inc_warning, reset_warnings, inc_mutes, add_memory, get_recent_memory, add_audit
from hafez import get_fal

# -------- Settings (from env) --------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
INFRACTION_LIMIT = int(os.getenv("INFRACTION_LIMIT", "5"))
MUTE_DURATION_HOURS = int(os.getenv("MUTE_DURATION_HOURS", "12"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MEMORY_LENGTH = int(os.getenv("MEMORY_LENGTH", "12"))
MEETUP_BOT_USERNAME = os.getenv("MEETUP_BOT_USERNAME", "@Meetupyazd_bot")

if not TELEGRAM_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN env is required")

# OpenAI client
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Load profanity list
def load_profanities():
    try:
        with open("profanity.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

PROFANITIES = load_profanities()

def normalize_fa(text: str) -> str:
    text = text.lower()
    repl = {
        "ي": "ی", "ك": "ک",
        "ۀ": "ه", "ة": "ه",
        "ؤ": "و", "أ": "ا", "إ": "ا",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    # remove diacritics and ZWNJ
    text = re.sub(r"[\u064B-\u065F\u0610-\u061A\u06D6-\u06ED\u200c]", "", text)
    return text

async def ensure_admin_notice(context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        if ADMIN_ID:
            await context.bot.send_message(chat_id=ADMIN_ID, text=text)
        elif ADMIN_USERNAME:
            await context.bot.send_message(chat_id=ADMIN_USERNAME, text=text)
    except Exception:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"سلام {user.first_name} 👋\nمن ربات میت‌آپ هوش مصنوعی‌ام؛ می‌تونی بهم بگی «ربات یه فال حافظ» یا «ربات یه جوک» یا با دستور /ai باهام گپ بزنی."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "دستورات:\n"
        "• /ai متن — گپ با هوش مصنوعی\n"
        "• /hafez — فال حافظ\n"
        "• /invite — دریافت لینک عضویت (درخواست بده تا برات بفرستم)\n"
        "• /addbadword کلمه — اضافه‌کردن کلمه نامناسب (ادمین)\n"
        "• /warns — دیدن اخطارهای خودت\n"
    )
    await update.message.reply_text(txt)

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        if m.is_bot:
            continue
        await update.message.reply_text(
            f"🎉 خوش اومدی {m.first_name} عزیز!\n"
            "اینجا با احترام و حال خوب کنار همیم. هر کمکی خواستی صدام کن: «ربات ...»"
        )

def contains_profanity(text: str) -> bool:
    if not text:
        return False
    t = normalize_fa(text)
    # simple token & substring check
    words = re.findall(r"[0-9\u0600-\u06FF\w]+", t)
    for w in words:
        for bad in PROFANITIES:
            if bad and bad in w:
                return True
    return False

async def handle_profanity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if message handled (muted/banned), else False"""
    msg = update.effective_message
    user = msg.from_user
    chat_id = msg.chat_id
    text = msg.text or msg.caption or ""

    if not contains_profanity(text):
        return False

    warnings, mutes = inc_warning(chat_id, user.id)
    await msg.reply_text(f"⚠️ {user.first_name} عزیز، لطفاً از واژه‌های محترمانه استفاده کن. اخطار {warnings}/{INFRACTION_LIMIT}")

    if warnings >= INFRACTION_LIMIT:
        # mute
        until = datetime.utcnow() + timedelta(hours=MUTE_DURATION_HOURS)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until
            )
            reset_warnings(chat_id, user.id)
            total_mutes = inc_mutes(chat_id, user.id)
            await msg.reply_text(f"🔇 {user.first_name} به مدت {MUTE_DURATION_HOURS} ساعت در سکوت قرار گرفت.")
            add_audit(chat_id, user.id, context.bot.id, "mute", "profanity_limit_reached")
            await ensure_admin_notice(context, f"🔔 سکوت کاربر @{user.username or user.id} به دلیل فحاشی در {chat_id}. مجموع سکوت‌ها: {total_mutes}")
            # if repeated mutes, ban
            if total_mutes >= 2:
                await context.bot.ban_chat_member(chat_id=chat_id, user_id=user.id)
                await msg.reply_text(f"⛔️ {user.first_name} به دلیل تکرار بی‌احترامی بن شد.")
                add_audit(chat_id, user.id, context.bot.id, "ban", "repeat_offender")
                await ensure_admin_notice(context, f"⛔️ کاربر @{user.username or user.id} بن شد (تکرار).")
        except Exception as e:
            await ensure_admin_notice(context, f"❗️نتوانستم کاربر را محدود کنم: {e}")
    return True

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    try:
        # Try to create a new invite link (requires admin)
        link = None
        try:
            inv = await context.bot.create_chat_invite_link(chat_id=chat.id, name=f"Request by {user.id}", creates_join_request=False)
            link = inv.invite_link
        except Exception:
            # fallback to the provided bot username
            link = f"https://t.me/{MEETUP_BOT_USERNAME.lstrip('@')}"
        await update.message.reply_text(f"🔗 لینک عضویت: {link}\n(در صورت نیاز برای امنیت، لینک فقط به درخواست ارسال می‌شود.)")
    except Exception as e:
        await update.message.reply_text("نتوانستم لینک بدهم. احتمالاً دسترسی ادمین ندارم.")

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if client is None:
        await update.message.reply_text("کلید OpenAI تنظیم نشده است.")
        return
    user = update.effective_user
    chat = update.effective_chat
    # message after /ai command
    user_text = " ".join(context.args) if context.args else (update.message.text or "")
    user_text = user_text.replace("/ai", "", 1).strip()

    if not user_text:
        await update.message.reply_text("متن سوالت رو بعد از /ai بنویس 🌱")
        return

    # build memory
    history = get_recent_memory(chat.id, user.id, limit=MEMORY_LENGTH)
    messages = [{"role": "system", "content": "تو یک دستیار فارسی‌زبان، صمیمی، محترم و گروهی هستی. کوتاه، روشن و دوستانه جواب بده."}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=400
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        reply = f"خطا در ارتباط با AI: {e}"

    await update.message.reply_text(reply)
    # save to memory
    add_memory(chat.id, user.id, "user", user_text)
    add_memory(chat.id, user.id, "assistant", reply)

async def hafez(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    poem = get_fal()
    await update.message.reply_text(f"بله {user.first_name} عزیزم:\n\n{poem}")

async def natural_triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle colloquial triggers like 'ربات فال حافظ' or 'ربات ...' or complaints"""
    msg = update.effective_message
    text = (msg.text or "").strip()
    if not text:
        return

    # complaint trigger (needs to be a reply)
    normalized = normalize_fa(text)
    complaint_phrases = ["اون محتواي غير اخلاقي فرستاد", "اون محتوای غیر اخلاقی فرستاد", "محتواي جنسي فرستاد", "محتوای جنسی فرستاد"]
    if any(p in normalized for p in [normalize_fa(p) for p in complaint_phrases]) and msg.reply_to_message:
        target: User = msg.reply_to_message.from_user
        until = datetime.utcnow() + timedelta(hours=MUTE_DURATION_HOURS)
        try:
            await context.bot.restrict_chat_member(
                chat_id=msg.chat_id,
                user_id=target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until
            )
            await msg.reply_text(f"🔇 @{target.username or target.first_name} به صورت موقت سکوت شد تا ادمین بررسی کند.")
            add_audit(msg.chat_id, target.id, msg.from_user.id, "mute_on_report", "reported_by_user")
            await ensure_admin_notice(context, f"📣 گزارش محتوای نامناسب: هدف @{target.username or target.id} / گزارش‌دهنده @{msg.from_user.username or msg.from_user.id}")
        except Exception as e:
            await msg.reply_text("نتوانستم سکوت کنم؛ احتمالاً ادمین نیستم.")
        return

    # Hafez trigger
    if re.search(r"(ربات|بات).*(فال|حافظ)", normalized):
        await hafez(update, context)
        return

    # AI trigger: messages that start with 'ربات' or bot mention
    entity_mentions = [e.user.username for e in (msg.entities or []) if getattr(e, "user", None)]
    if normalized.startswith("ربات") or (context.bot.username and f"@{context.bot.username.lower()}" in normalized) or (context.bot.username in entity_mentions if entity_mentions else False):
        # remove the 'ربات' keyword
        cleaned = re.sub(r"^(ربات|بات)\s*", "", text, flags=re.IGNORECASE)
        update_cpy = Update.de_json(update.to_dict(), context.bot)
        update_cpy.message.text = "/ai " + cleaned
        await ai_chat(update_cpy, context)
        return

async def warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # show user's warnings (simple read from DB)
    from memory import sqlite3, DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT warnings, mutes FROM warnings WHERE chat_id=? AND user_id=?", (update.effective_chat.id, update.effective_user.id))
        row = c.fetchone()
    warns = row[0] if row else 0
    mutes = row[1] if row else 0
    await update.message.reply_text(f"اخطارها: {warns}/{INFRACTION_LIMIT} | سکوت‌ها: {mutes}")

async def add_badword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("فقط ادمین می‌تواند اضافه کند.")
        return
    if not context.args:
        await update.message.reply_text("استفاده: /addbadword کلمه")
        return
    word = " ".join(context.args).strip()
    PROFANITIES.add(word)
    with open("profanity.json", "w", encoding="utf-8") as f:
        json.dump(sorted(list(PROFANITIES)), f, ensure_ascii=False, indent=2)
    await update.message.reply_text(f"✅ اضافه شد: {word}")

async def group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # First, moderation
    handled = await handle_profanity(update, context)
    if handled:
        return
    # Otherwise, let natural triggers handle
    await natural_triggers(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await ensure_admin_notice(context, f"⚠️ خطا: {context.error}")
    except Exception:
        pass

async def main():
    os.makedirs("data", exist_ok=True)
    init_db()
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("ai", ai_chat))
    application.add_handler(CommandHandler("hafez", hafez))
    application.add_handler(CommandHandler("invite", invite))
    application.add_handler(CommandHandler("warns", warns))
    application.add_handler(CommandHandler("addbadword", add_badword))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_text))

    application.add_error_handler(error_handler)

    # Run long-polling (ساده‌ترین روش روی Railway)
await application.initialize()
me = await application.bot.get_me()
print(f"Bot started as @{me.username}")
await application.start()
await application.run_polling()
