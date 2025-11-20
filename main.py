# bot.py
"""
Telegram Password Generator Bot
- Uses inline keyboards to let users pick length and character sets
- Generates secure random passwords using Python's `secrets`
- Minimal, production-minded structure (env config, logging)
"""

import os
import logging
import html
from typing import Dict, Any
from secrets import choice as secure_choice
from string import ascii_lowercase, ascii_uppercase, digits, punctuation

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ---- Logging ----
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("pwgen-bot")

# ---- Config ----
TOKEN = os.getenv("TG_BOT_TOKEN")
if not TOKEN:
    logger.error("TG_BOT_TOKEN environment variable not set. Exiting.")
    raise SystemExit("TG_BOT_TOKEN required")

# Default settings per user (in-memory). For production replace with DB.
USER_SETTINGS: Dict[int, Dict[str, Any]] = {}

# Default values
DEFAULTS = {
    "length": 12,
    "upper": True,
    "lower": True,
    "digits": True,
    "symbols": False,
    # store last generated password to allow "regenerate" behavior
    "last_password": None,
}

# ---- Helpers ----
def get_user_settings(user_id: int) -> Dict[str, Any]:
    if user_id not in USER_SETTINGS:
        USER_SETTINGS[user_id] = DEFAULTS.copy()
    return USER_SETTINGS[user_id]

def build_main_keyboard(settings: Dict[str, Any]) -> InlineKeyboardMarkup:
    # Length buttons row
    lengths = [8, 12, 16, 24]
    row_lengths = [
        InlineKeyboardButton(
            f"{'✅' if settings['length'] == l else '⬜️'} {l}",
            callback_data=f"len:{l}",
        )
        for l in lengths
    ]

    # Toggle row for charset
    toggles = [
        InlineKeyboardButton(
            f"{'✅' if settings['upper'] else '⬜️'} Upper",
            callback_data="toggle:upper",
        ),
        InlineKeyboardButton(
            f"{'✅' if settings['lower'] else '⬜️'} Lower",
            callback_data="toggle:lower",
        ),
    ]
    toggles2 = [
        InlineKeyboardButton(
            f"{'✅' if settings['digits'] else '⬜️'} Digits",
            callback_data="toggle:digits",
        ),
        InlineKeyboardButton(
            f"{'✅' if settings['symbols'] else '⬜️'} Symbols",
            callback_data="toggle:symbols",
        ),
    ]

    # Action row
    actions = [
        InlineKeyboardButton("🔁 Generate", callback_data="action:generate"),
        InlineKeyboardButton("♻️ Regenerate", callback_data="action:regenerate"),
        InlineKeyboardButton("🗑️ Clear", callback_data="action:clear"),
    ]

    # Help / share row
    small = [
        InlineKeyboardButton("ℹ️ Help", callback_data="action:help"),
        InlineKeyboardButton("🔗 Share", switch_inline_query=""),  # allow sharing bot
    ]

    keyboard = [
        row_lengths,
        toggles,
        toggles2,
        actions,
        small,
    ]
    return InlineKeyboardMarkup(keyboard)

def secure_password(length: int, use_upper: bool, use_lower: bool, use_digits: bool, use_symbols: bool) -> str:
    pool = ""
    if use_lower:
        pool += ascii_lowercase
    if use_upper:
        pool += ascii_uppercase
    if use_digits:
        pool += digits
    if use_symbols:
        # remove problematic whitespace-like chars from punctuation if any
        pool += "".join(ch for ch in punctuation if ch not in ('`', '´', '¨', ' '))  

    if not pool:
        raise ValueError("Character pool is empty. Enable at least one character set.")

    # Ensure at least one character from each selected category appears (best-effort)
    password_chars = []

    if use_lower:
        password_chars.append(secure_choice(ascii_lowercase))
    if use_upper:
        password_chars.append(secure_choice(ascii_uppercase))
    if use_digits:
        password_chars.append(secure_choice(digits))
    if use_symbols:
        password_chars.append(secure_choice("".join(ch for ch in punctuation if ch not in ('`', '´', '¨', ' '))))

    # fill remaining
    while len(password_chars) < length:
        password_chars.append(secure_choice(pool))

    # shuffle securely
    # simple secure shuffle: Fisher-Yates using secrets
    for i in range(len(password_chars) - 1, 0, -1):
        j = secure_choice(range(i + 1))
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return "".join(password_chars[:length])

# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    settings = get_user_settings(user.id)
    text = (
        "🔐 *Password Generator*\n\n"
        "Use the buttons to choose password length and character sets. Then press Generate.\n\n"
        f"*Current length:* {settings['length']}\n"
        f"*Upper:* {'Yes' if settings['upper'] else 'No'}  "
        f"*Lower:* {'Yes' if settings['lower'] else 'No'}\n"
        f"*Digits:* {'Yes' if settings['digits'] else 'No'}  "
        f"*Symbols:* {'Yes' if settings['symbols'] else 'No'}"
    )
    await update.message.reply_text(
        text,
        reply_markup=build_main_keyboard(settings),
        parse_mode="Markdown",
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "How to use:\n"
        "• Tap a length button to set password length.\n"
        "• Toggle Upper/Lower/Digits/Symbols to include/exclude character sets.\n"
        "• Press *Generate* to create a password.\n"
        "• Press *Regenerate* to make another password with same settings.\n"
        "• Press *Clear* to clear stored last password.\n\n"
        "Security tip: don't share generated passwords in public chats. Use private chat."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /help.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # acknowledge callback right away
    user_id = query.from_user.id
    settings = get_user_settings(user_id)
    data = query.data or ""

    # parse actions
    if data.startswith("len:"):
        try:
            new_len = int(data.split(":", 1)[1])
            settings["length"] = new_len
            await query.edit_message_text(
                text=build_status_text(settings),
                reply_markup=build_main_keyboard(settings),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.exception("Failed setting length: %s", e)
            await query.edit_message_text("Failed to set length.")
        return

    if data.startswith("toggle:"):
        key = data.split(":", 1)[1]
        if key in ("upper", "lower", "digits", "symbols"):
            # toggle boolean
            settings[key] = not settings.get(key, False)
            await query.edit_message_text(
                text=build_status_text(settings),
                reply_markup=build_main_keyboard(settings),
                parse_mode="Markdown",
            )
        else:
            await query.answer("Unknown toggle.", show_alert=True)
        return

    if data.startswith("action:"):
        action = data.split(":", 1)[1]
        if action == "generate":
            try:
                pwd = secure_password(
                    length=settings["length"],
                    use_upper=settings["upper"],
                    use_lower=settings["lower"],
                    use_digits=settings["digits"],
                    use_symbols=settings["symbols"],
                )
                settings["last_password"] = pwd
                # send password as reply (not edited) to keep a clear record for user
                await query.message.reply_text(
                    f"🔐 *Generated password:*\n`{html.escape(pwd)}`",
                    parse_mode="Markdown",
                )
                # update main message so UI still reflects settings
                await query.edit_message_text(
                    text=build_status_text(settings),
                    reply_markup=build_main_keyboard(settings),
                    parse_mode="Markdown",
                )
            except ValueError as e:
                await query.answer(str(e), show_alert=True)
            except Exception as e:
                logger.exception("Generation error: %s", e)
                await query.answer("Error generating password.", show_alert=True)
            return

        if action == "regenerate":
            if not settings.get("last_password"):
                # act like generate
                await query.answer("No previous password found — generating new.", show_alert=False)
            try:
                pwd = secure_password(
                    length=settings["length"],
                    use_upper=settings["upper"],
                    use_lower=settings["lower"],
                    use_digits=settings["digits"],
                    use_symbols=settings["symbols"],
                )
                settings["last_password"] = pwd
                await query.message.reply_text(
                    f"🔁 *Regenerated password:*\n`{html.escape(pwd)}`",
                    parse_mode="Markdown",
                )
                await query.edit_message_text(
                    text=build_status_text(settings),
                    reply_markup=build_main_keyboard(settings),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.exception("Regenerate error: %s", e)
                await query.answer("Failed to regenerate.", show_alert=True)
            return

        if action == "clear":
            settings["last_password"] = None
            await query.answer("Cleared last password.", show_alert=False)
            await query.edit_message_text(
                text=build_status_text(settings),
                reply_markup=build_main_keyboard(settings),
                parse_mode="Markdown",
            )
            return

        if action == "help":
            await query.answer()  # silent
            await query.message.reply_text(
                "Tap length buttons and toggles, then Generate. /help for more details."
            )
            return

    # unknown callback
    await query.answer("Unknown action.", show_alert=True)

def build_status_text(settings: Dict[str, Any]) -> str:
    return (
        "🔐 *Password Generator — Settings*\n\n"
        f"*Length:* {settings['length']}\n"
        f"*Upper:* {'Yes' if settings['upper'] else 'No'}\n"
        f"*Lower:* {'Yes' if settings['lower'] else 'No'}\n"
        f"*Digits:* {'Yes' if settings['digits'] else 'No'}\n"
        f"*Symbols:* {'Yes' if settings['symbols'] else 'No'}\n\n"
        "Use the buttons below to modify settings or generate a password."
    )

# ---- Startup ----
def register_commands(application):
    commands = [
        BotCommand("start", "Open password generator UI"),
        BotCommand("help", "Usage instructions"),
    ]
    application.bot.set_my_commands(commands)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["help"], help_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    register_commands(app)

    logger.info("Starting Password Generator Bot (polling).")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by signal.")
