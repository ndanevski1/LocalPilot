"""
LocalPilot — On-Device Personal Action Agent
Telegram Remote Interface Daemon
"""

import os
import platform
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("LocalPilot")

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()


def check_auth(update: Update) -> bool:
    """Verifies if the sender is authorized to communicate with LocalPilot."""
    if not ALLOWED_USER_ID:
        # Initial setup mode: allow anyone so the owner can discover their user ID
        return True
    user = update.effective_user
    if user and str(user.id) == ALLOWED_USER_ID:
        return True
    return False


async def unauthorized_warning(update: Update) -> None:
    """Alerts unauthorized users that access is restricted."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "⛔ *Access Denied*\n"
            "This LocalPilot instance is locked to a private host machine.",
            parse_mode="Markdown",
        )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    user = update.effective_user
    user_id = user.id if user else "Unknown"
    first_name = user.first_name if user else "Operator"

    auth_status = "🔒 Locked" if ALLOWED_USER_ID else "⚠️ Setup Mode (Open)"

    keyboard = [
        [
            InlineKeyboardButton("📊 System Status", callback_data="status"),
            InlineKeyboardButton("🛡️ Test HITL Approval", callback_data="demo_hitl"),
        ],
        [
            InlineKeyboardButton("❓ Help & Commands", callback_data="help"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 *Hello, {first_name}!*\n\n"
        f"🤖 Welcome to **LocalPilot** — your on-device personal action agent.\n\n"
        f"📋 *Session Info:*\n"
        f"• **Your User ID:** `{user_id}`\n"
        f"• **Security Gate:** {auth_status}\n"
    )

    if not ALLOWED_USER_ID:
        welcome_text += (
            f"\n💡 *Security Setup Tip:*\n"
            f"To restrict this bot exclusively to you, set:\n"
            f"`TELEGRAM_ALLOWED_USER_ID={user_id}`\n"
            f"in your `.env` file on the host computer.\n"
        )

    welcome_text += "\nSelect an option below or send any instruction to test the agent:"
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /status command."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    node = platform.node()
    system = f"{platform.system()} {platform.release()}"
    python_ver = platform.python_version()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_message = (
        f"📊 *LocalPilot Host Status*\n\n"
        f"• **Status:** 🟢 Online & Listening\n"
        f"• **Host Node:** `{node}`\n"
        f"• **OS Platform:** `{system}`\n"
        f"• **Python Core:** `v{python_ver}`\n"
        f"• **Host Time:** `{now_str}`\n"
        f"• **Outbound Link:** Secure Polling (No open ports)"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(status_message, parse_mode="Markdown")
    else:
        await update.message.reply_text(status_message, parse_mode="Markdown")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /help command."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    help_text = (
        "📖 *LocalPilot Command Reference*\n\n"
        "• `/start` - Launch or reset the session menu\n"
        "• `/status` - Check host connectivity & system health\n"
        "• `/demo_hitl` - Simulate a Human-in-the-Loop approval gate\n"
        "• `/help` - View this reference card\n\n"
        "💬 *Action Prompts:*\n"
        "You can also send natural language instructions (e.g., _\"Summarize today's unread emails\"_ or _\"Search Amazon for USB-C cable\"_) to test agent message handling."
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(help_text, parse_mode="Markdown")
    else:
        await update.message.reply_text(help_text, parse_mode="Markdown")


async def demo_hitl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Demonstrates Module 3: Human-in-the-Loop (HITL) Gatekeeper."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve Action", callback_data="hitl_approve"),
            InlineKeyboardButton("❌ Reject / Abort", callback_data="hitl_reject"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    card = (
        "⚠️ *Human-in-the-Loop Gatekeeper Triggered*\n"
        "_(LocalPilot Module 3 Simulation)_\n\n"
        "The agent has paused a state-changing operation awaiting your explicit authorization:\n\n"
        "• **Operation:** Place Web Order\n"
        "• **Vendor:** Amazon.com\n"
        "• **Item:** Anker 6ft Braided USB-C Cable (Pack of 2)\n"
        "• **Price:** `$14.99`\n"
        "• **Card:** Stored in Local Vault (Zero-Trust Tokenized)\n\n"
        "Please confirm or cancel this action:"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(card, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(card, reply_markup=reply_markup, parse_mode="Markdown")


async def callback_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes interactive button presses."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    data = query.data
    if data == "status":
        await status_handler(update, context)
    elif data == "demo_hitl":
        await demo_hitl_handler(update, context)
    elif data == "help":
        await help_handler(update, context)
    elif data == "hitl_approve":
        await query.edit_message_text(
            "✅ *Action Approved by Operator*\n\n"
            "LocalPilot resumed execution: decrypted credentials injected locally, order simulated successfully.",
            parse_mode="Markdown",
        )
    elif data == "hitl_reject":
        await query.edit_message_text(
            "❌ *Action Rejected by Operator*\n\n"
            "LocalPilot aborted operation. No payment was made and no external requests were dispatched.",
            parse_mode="Markdown",
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes natural language input sent by the operator."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    user_text = update.message.text
    logger.info(f"Incoming user instruction: {user_text}")

    response = (
        f"🤖 *LocalPilot Core Received:*\n"
        f"> \"_{user_text}_\"\n\n"
        f"⚙️ *Pipeline Dispatch:*\n"
        f"• Task queued for intent classification\n"
        f"• Model router: On-device vs. Cloud orchestration\n"
        f"• Execution engine: Ready for Playwright / Gmail REST module\n\n"
        f"_(Full autonomous reasoning loop will connect to this handler)_"
    )
    await update.message.reply_text(response, parse_mode="Markdown")


def main() -> None:
    """Initializes and runs the Telegram Bot polling daemon."""
    if not BOT_TOKEN or BOT_TOKEN.startswith("your_"):
        logger.error("Missing or invalid TELEGRAM_BOT_TOKEN in .env file!")
        print("Error: Please specify TELEGRAM_BOT_TOKEN in your .env file.")
        return

    logger.info("Initializing LocalPilot Telegram Bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("demo_hitl", demo_hitl_handler))

    # Register Callback & Message Handlers
    app.add_handler(CallbackQueryHandler(callback_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    logger.info("LocalPilot Telegram Bot is running (Long-polling active)...")
    logger.info("Press Ctrl+C to terminate the daemon.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
