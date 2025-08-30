# MeetupAI Telegram Group Bot (Railway)

ربات گروهی تلگرام با امکانات:
- گپ هوش مصنوعی به صورت عامیانه (`/ai` یا گفتن «ربات ...»)
- فال حافظ (`/hafez` یا «ربات فال حافظ»)
- خوش‌آمدگویی صمیمی به اعضای جدید
- فیلتر فحاشی + اخطار خودکار، سکوت پس از n اخطار، و بن در تکرار
- رسیدگی سریع به گزارش محتوای غیراخلاقی: اگر روی پیام کسی ریپلای کنی و بنویسی «اون محتوای غیر اخلاقی فرستاد»، ربات آن فرد را موقت سکوت می‌کند و به ادمین خبر می‌دهد
- لینک عضویت فقط در صورت درخواست (`/invite`)

## نصب محلی
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export OPENAI_API_KEY=...
python bot.py
```

## دیپلوی روی Railway (long polling)
1) یک ریپوی گیت‌هاب بساز و این پروژه را پوش کن.
2) در Railway پروژه جدید با **Deploy from GitHub** بساز.
3) در تب **Variables** مقادیر زیر را اضافه کن (از روی `.env.example`):
   - TELEGRAM_BOT_TOKEN
   - OPENAI_API_KEY
   - ADMIN_ID (عددی)
   - ADMIN_USERNAME (مثلاً @AlirezaA029)
   - INFRACTION_LIMIT، MUTE_DURATION_HOURS، MEMORY_LENGTH (دلخواه)
   - MEETUP_BOT_USERNAME (مثلاً @Meetupyazd_bot)
4) در تب **Services → Deployments** مطمئن شو که Railway `Procfile` را تشخیص داده (worker).
5) بعد از دیپلوی، ربات را به گروه اضافه کن و دسترسی‌های ادمین لازم را بده: Restrict Members, Ban Users, Manage Chat.
6) تست سریع:
   - بنویس «ربات یه فال حافظ»
   - بنویس `/ai سلام، حالت چطوره؟`
   - یک کلمه از `profanity.json` را امتحان کن تا اخطار بده.

### شخصی‌سازی
- لیست کلمات نامناسب: فایل `profanity.json` را ویرایش کن یا با `/addbadword کلمه` (فقط ادمین) اضافه کن.
- متن خوش‌آمدگویی و پاسخ‌ها داخل `bot.py` مشخص شده‌اند—هرطور دوست داری تغییر بده.
- حافظ: فایل `hafez.py` را با اشعار بیشتر کامل کن.

> نکته امنیتی: هرگز توکن‌ها را داخل کد/ریپو قرار نده. آن‌ها را فقط در Environment Variables ست کن.
