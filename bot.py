"""
LocalPilot — On-Device Personal Action Agent
Telegram Remote Interface Daemon
"""

import os
import platform
import logging
import asyncio
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

import gmail_service

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


def build_menu_markup() -> InlineKeyboardMarkup:
    """Dynamically builds the interactive main menu depending on Gmail connection state."""
    gmail_connected = gmail_service.is_connected()

    if gmail_connected:
        gmail_btn = InlineKeyboardButton("📬 Unread Email Digest", callback_data="summary")
        opt_btn = InlineKeyboardButton("🔌 Disconnect Gmail", callback_data="disconnect_gmail")
    else:
        gmail_btn = InlineKeyboardButton("🔗 Connect Gmail", callback_data="connect_gmail")
        opt_btn = InlineKeyboardButton("ℹ️ Gmail: Offline", callback_data="gmail_info")

    keyboard = [
        [gmail_btn, InlineKeyboardButton("📊 System Status", callback_data="status")],
        [InlineKeyboardButton("🛡️ Test HITL Approval", callback_data="demo_hitl"), opt_btn],
        [InlineKeyboardButton("❓ Help & Commands", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    user = update.effective_user
    user_id = user.id if user else "Unknown"
    first_name = user.first_name if user else "Operator"

    auth_status = "🔒 Locked" if ALLOWED_USER_ID else "⚠️ Setup Mode (Open)"

    # Check Gmail integration state
    if gmail_service.is_connected():
        email_addr = gmail_service.get_connected_email() or "Authorized Account"
        gmail_status = f"🟢 Connected (`{email_addr}`)"
    else:
        gmail_status = "⚪ Not Connected (Optional)"

    reply_markup = build_menu_markup()

    welcome_text = (
        f"👋 *Hello, {first_name}!*\n\n"
        f"🤖 Welcome to **LocalPilot** — your on-device personal action agent.\n\n"
        f"📋 *Session Info:*\n"
        f"• **Your User ID:** `{user_id}`\n"
        f"• **Security Gate:** {auth_status}\n"
        f"• **Gmail Engine:** {gmail_status}\n"
    )

    if not ALLOWED_USER_ID:
        welcome_text += (
            f"\n💡 *Security Setup Tip:*\n"
            f"To restrict this bot exclusively to you, set:\n"
            f"`TELEGRAM_ALLOWED_USER_ID={user_id}`\n"
            f"in your `.env` file on the host computer.\n"
        )

    welcome_text += "\nSelect an option below or send an instruction to test the agent:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
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

    if gmail_service.is_connected():
        email_addr = gmail_service.get_connected_email() or "Google User"
        gmail_status = f"🟢 Connected (`{email_addr}`)"
    else:
        gmail_status = "⚪ Disconnected (Run /connect_gmail)"

    status_message = (
        f"📊 *LocalPilot Host Status*\n\n"
        f"• **Status:** 🟢 Online & Listening\n"
        f"• **Host Node:** `{node}`\n"
        f"• **OS Platform:** `{system}`\n"
        f"• **Python Core:** `v{python_ver}`\n"
        f"• **Host Time:** `{now_str}`\n"
        f"• **Gmail Engine:** {gmail_status}\n"
        f"• **Outbound Link:** Secure Polling (No open ports)"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(status_message, parse_mode="Markdown")
    else:
        await update.message.reply_text(status_message, parse_mode="Markdown")


async def connect_gmail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles initiating the Google OAuth 2.0 flow."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    if gmail_service.is_connected():
        email = gmail_service.get_connected_email() or "authenticated user"
        msg = f"✅ Gmail is already connected as `{email}`.\nUse `/summary` to fetch unread emails or `/disconnect_gmail` to opt out."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return

    prompt_msg = (
        "🌐 *Connect Gmail via Google OAuth 2.0*\n\n"
        "Because LocalPilot runs as a secure background daemon on Windows, interactive browser windows cannot be launched directly from background tasks.\n\n"
        "💻 *To connect in 10 seconds:*\n"
        "1. Open your terminal in VS Code (`Ctrl + ~`)\n"
        "2. Run:\n"
        "   `python setup_gmail.py`\n"
        "3. Your browser will open immediately. Choose your account and grant Read-Only access!\n\n"
        "Once complete, tap `/start` or send `/summary` to test your inbox digest."
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(prompt_msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(prompt_msg, parse_mode="Markdown")


async def disconnect_gmail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles opting out and disconnecting Gmail."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    success, message = await asyncio.to_thread(gmail_service.disconnect)
    resp = f"🔌 *Gmail Status:* {message}"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(resp, reply_markup=build_menu_markup(), parse_mode="Markdown")
    else:
        await update.message.reply_text(resp, reply_markup=build_menu_markup(), parse_mode="Markdown")


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays an email digest of unread primary inbox messages."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    if not gmail_service.is_connected():
        resp = (
            "📭 *Gmail is not connected*\n\n"
            "To enable automated inbox summaries, tap **Connect Gmail** or send `/connect_gmail`."
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Connect Gmail Now", callback_data="connect_gmail")]])
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(resp, reply_markup=markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(resp, reply_markup=markup, parse_mode="Markdown")
        return

    loading_msg = "🔍 *Scanning unread emails in your primary inbox...*"
    if update.callback_query:
        await update.callback_query.answer()
        msg_ref = await update.callback_query.message.reply_text(loading_msg, parse_mode="Markdown")
    else:
        msg_ref = await update.message.reply_text(loading_msg, parse_mode="Markdown")

    success, emails, info = await asyncio.to_thread(gmail_service.get_unread_emails, 5)

    if not success:
        await msg_ref.edit_text(f"❌ *Failed to retrieve emails:*\n{info}", parse_mode="Markdown")
        return

    digest = gmail_service.format_email_digest(emails)
    await msg_ref.edit_text(digest, parse_mode="Markdown")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /help command."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    help_text = (
        "📖 *LocalPilot Command Reference*\n\n"
        "• `/start` - Launch or refresh the main interactive menu\n"
        "• `/status` - Check host connectivity, system health & Gmail status\n"
        "• `/summary` - Fetch and summarize latest unread emails\n"
        "• `/connect_gmail` - Connect your Google account via OAuth 2.0\n"
        "• `/disconnect_gmail` - Opt-out and delete local Google session token\n"
        "• `/demo_hitl` - Simulate a Human-in-the-Loop approval gate\n"
        "• `/help` - View this reference card\n\n"
        "💬 *Action Prompts:*\n"
        "You can also send natural language text like _\"Give me an email summary\"_ or _\"Check unread mail\"_ directly in this chat."
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

    data = query.data
    if data == "status":
        await status_handler(update, context)
    elif data == "connect_gmail":
        await connect_gmail_handler(update, context)
    elif data == "disconnect_gmail":
        await disconnect_gmail_handler(update, context)
    elif data == "summary":
        await summary_handler(update, context)
    elif data == "demo_hitl":
        await demo_hitl_handler(update, context)
    elif data == "help":
        await help_handler(update, context)
    elif data == "gmail_info":
        await query.answer()
        await query.message.reply_text(
            "ℹ️ *Gmail Engine is currently offline.*\nTap **Connect Gmail** to authenticate your account.",
            parse_mode="Markdown",
        )
    elif data == "hitl_approve":
        await query.answer()
        await query.edit_message_text(
            "✅ *Action Approved by Operator*\n\n"
            "LocalPilot resumed execution: decrypted credentials injected locally, order simulated successfully.",
            parse_mode="Markdown",
        )
    elif data == "hitl_reject":
        await query.answer()
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

    user_text = update.message.text.strip().lower()
    logger.info(f"Incoming user instruction: {user_text}")

    # Natural language dispatch for email summaries
    if any(keyword in user_text for keyword in ["email", "summary", "digest", "inbox", "mail"]):
        await summary_handler(update, context)
        return

    response = (
        f"🤖 *LocalPilot Core Received:*\n"
        f"> \"_{update.message.text}_\"\n\n"
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

    logger.info("Initializing LocalPilot Telegram Bot with Gmail Engine...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("connect_gmail", connect_gmail_handler))
    app.add_handler(CommandHandler("disconnect_gmail", disconnect_gmail_handler))
    app.add_handler(CommandHandler("demo_hitl", demo_hitl_handler))

    # Register Callback & Message Handlers
    app.add_handler(CallbackQueryHandler(callback_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    logger.info("LocalPilot Telegram Bot is running (Long-polling active)...")
    logger.info("Press Ctrl+C to terminate the daemon.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
