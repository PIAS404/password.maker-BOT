# bot.py
import os
import logging
from secrets import choice as secure_choice
from string import ascii_lowercase, ascii_uppercase, digits, punctuation

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TG_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Error: TG_BOT_TOKEN not found in env.")

USER = {}  # simple storage


def settings_of(user_id):
    if user_id not in USER:
        USER[user_id] = {
            "length": 12,
            "upper": True,
            "lower": True,
            "digits": True,
            "symbols": False,
            "last": None,
        }
    return USER[user_id]


def keyboard(settings):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'✅' if settings['length']==8 else '⬜️'} 8", callback_data="len:8"
            ),
            InlineKeyboardButton(
                f"{'✅' if settings['length']==12 else '⬜️'} 12", callback_data="len:12"
            ),
            InlineKeyboardButton(
                f"{'✅' if settings['length']==16 else '⬜️'} 16", callback_data="len:16"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if settings['upper'] else '⬜️'} Upper", callback_data="toggle:upper"
            ),
            InlineKeyboardButton(
                f"{'✅' if settings['lower'] else '⬜️'} Lower", callback_data="toggle:lower"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if settings['digits'] else '⬜️'} Digits", callback_data="toggle:digits"
            ),
            InlineKeyboardButton(
                f"{'✅' if settings['symbols'] else '⬜️'} Symbols", callback_data="toggle:symbols"
            ),
        ],
        [
            InlineKeyboardButton("🔁 Generate", callback_data="do:gen"),
            InlineKeyboardButton("♻️ Again", callback_data="do:regen"),
        ],
    ])


def pw_gen(length, u, l, d, s):
    pool = ""
    if l:
        pool += ascii_lowercase
    if u:
        pool += ascii_uppercase
    if d:
        pool += digits
    if s:
        pool += "".join(ch for ch in punctuation if ch not in ('`', ' ', '´'))

    if not pool:
        return "Enable at least one charset."

    return "".join(secure_choice(pool) for _ in range(length))


def status(settings):
    return (
        "🔐 *Password Generator*\n\n"
        f"*Length:* {settings['length']}\n"
        f"*Upper:* {settings['upper']}\n"
        f"*Lower:* {settings['lower']}\n"
        f"*Digits:* {settings['digits']}\n"
        f"*Symbols:* {settings['symbols']}\n\n"
        "Choose options below 👇"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    s = settings_of(user)
    await update.message.reply_text(
        status(s),
        reply_markup=keyboard(s),
        parse_mode="Markdown",
    )


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.id
    s = settings_of(user)
    data = query.data

    if data.startswith("len:"):
        s["length"] = int(data.split(":")[1])

    elif data.startswith("toggle:"):
        key = data.split(":")[1]
        s[key] = not s[key]

    elif data == "do:gen":
        pwd = pw_gen(s["length"], s["upper"], s["lower"], s["digits"], s["symbols"])
        s["last"] = pwd
        await query.message.reply_text(f"`{pwd}`", parse_mode="Markdown")

    elif data == "do:regen":
        if not s["last"]:
            pwd = pw_gen(s["length"], s["upper"], s["lower"], s["digits"], s["symbols"])
        else:
            pwd = pw_gen(s["length"], s["upper"], s["lower"], s["digits"], s["symbols"])
        s["last"] = pwd
        await query.message.reply_text(f"`{pwd}`", parse_mode="Markdown")

    await query.edit_message_text(
        status(s),
        reply_markup=keyboard(s),
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, ctx):
    await update.message.reply_text("Use /start to begin.")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(callback))

    # IMPORTANT: run_polling directly (no asyncio.run here)
    app.run_polling()


if __name__ == "__main__":
    main()
