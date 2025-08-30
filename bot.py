import os
import json
import random
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from openai import AsyncOpenAI


# ========= تنظیمات ========= #
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
INFRACTION_LIMIT = int(os.getenv("INFRACTION_LIMIT", "5"))
MUTE_DURATION_HOURS = int(os.getenv("MUTE_DURATION_HOURS", "12"))
MEETUP_BOT_USERNAME = os.getenv("MEETUP_BOT_USERNAME", "")

# کلاینت OpenAI
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ========= دیتابیس برای اخطار ========= #
DB_FILE = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER,
                count INTEGER,
                last_update TIMESTAMP
            )"""
    )
    conn.commit()
    conn.close()

init_db()

def get_warnings(user_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT count FROM warnings WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_warning(user_id: int) -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now()
    count = get_warnings(user_id)
    if count:
        c.execute("UPDATE warnings SET count = ?, last_update = ? WHERE user_id = ?", (count+1, now, user_id))
    else:
        c.execute("INSERT INTO warnings (user_id, count, last_update) VALUES (?, ?, ?)", (1, now, user_id))
    conn.commit()
    conn.close()
    return get_warnings(user_id)

def reset_warnings(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM warnings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ========= فیلتر فحش ========= #
with open("profanity.json", "r", encoding="utf-8") as f:
    BAD_WORDS = set(json.load(f))


def contains_bad_word(text: str) -> bool:
    return any(bad in text.lower() for bad in BAD_WORDS)


# ========= هندلرها ========= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋 من یک ربات هوش مصنوعی هستم.\n"
        "می‌تونی باهام چت کنی، فال حافظ بگیری یا ازم سوال بپرسی."
    )


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"🌹 خوش اومدی {member.mention_html()} عزیز! امیدوارم لحظات خوبی اینجا داشته باشی.",
            parse_mode="HTML",
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user

    # چک فحش
    if contains_bad_word(text):
        warns = add_warning(user.id)
        if warns < INFRACTION_LIMIT:
            await update.message.reply_text(
                f"⚠️ {user.mention_html()} عزیز، لطفاً رعایت کن. اخطار {warns}/{INFRACTION_LIMIT}",
                parse_mode="HTML",
            )
        else:
            until = datetime.now() + timedelta(hours=MUTE_DURATION_HOURS)
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            await update.message.reply_text(
                f"⛔ {user.mention_html()} به دلیل تکرار بی‌احترامی سکوت شد.",
                parse_mode="HTML",
            )
            reset_warnings(user.id)
        return

    # درخواست فال حافظ
    if "فال حافظ" in text:
        await hafez_handler(update, context)
        return

    # درخواست لینک
    if "لینک عضویت" in text:
        await invite(update, context)
        return

    # شروع مکالمه عامیانه با ربات
    if text.startswith("ربات"):
        await ai_handler(update, context)
        return


async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    target = update.message.reply_to_message.from_user

    text = update.message.text
    if "محتوای غیر اخلاقی" in text or "محتوای جنسی" in text:
        until = datetime.now() + timedelta(hours=MUTE_DURATION_HOURS)
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target.id,
            ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📢 کاربر {target.mention_html()} به دلیل گزارش محتوا سکوت شد.\nگروه: {update.effective_chat.title}",
            parse_mode="HTML",
        )


async def hafez_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poems = [
        "درخت دوستی بنشان که کام دل به بار آرد 🌹",
        "هر که را خوابگه آخر مشتی خاک است 🪶",
        "به هر که دل بسپاری، به همان رنگ شوی ✨",
        "از صدای سخن عشق ندیدم خوشتر 🎶",
    ]
    poem = random.choice(poems)
    user = update.effective_user
    await update.message.reply_text(f"بله {user.first_name} عزیزم:\n\n{poem}")


async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "تو یک ربات صمیمی تلگرام هستی که عامیانه و دوستانه جواب میده."},
                {"role": "user", "content": text},
            ],
        )
        answer = resp.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception:
        await update.message.reply_text("❌ خطا در ارتباط با هوش مصنوعی.")


async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if MEETUP_BOT_USERNAME:
        await update.message.reply_text(f"🔗 لینک عضویت: {MEETUP_BOT_USERNAME}")
    else:
        await update.message.reply_text("❌ لینک عضویت در تنظیمات ربات تعریف نشده.")


# ========= main ========= #
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hafez", hafez_handler))
    application.add_handler(CommandHandler("ai", ai_handler))
    application.add_handler(CommandHandler("invite", invite))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, report_handler))

    print("✅ Bot started!")
    application.run_polling()


if __name__ == "__main__":
    main()
