"""
LocalPilot — On-Device Personal Action Agent
Telegram Remote Interface Daemon
"""

import os
import platform
import logging
import asyncio
from datetime import datetime
from typing import Optional
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
import browser_service

# Configure logging to both console and a persistent local file
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "localpilot.log")

logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
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
        [InlineKeyboardButton("🌐 Call Browser", callback_data="call_browser"), InlineKeyboardButton("🛡️ Test HITL Approval", callback_data="demo_hitl")],
        [opt_btn, InlineKeyboardButton("❓ Help & Commands", callback_data="help")],
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
        gmail_status = "⚪ Disconnected (Run `/connect_gmail`)"

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
        await _safe_answer_query(update.callback_query)
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


async def _safe_answer_query(query, text=None, show_alert=False) -> None:
    """Safely responds to Telegram callback queries, silently ignoring expired query errors."""
    if not query:
        return
    try:
        if text:
            await query.answer(text=text, show_alert=show_alert)
        else:
            await query.answer()
    except Exception:
        pass


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
        await _safe_answer_query(update.callback_query)
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
    elif data == "call_browser":
        await call_browser_handler(update, context)
    elif data == "demo_hitl":
        await demo_hitl_handler(update, context)
    elif data == "help":
        await help_handler(update, context)
    elif data == "gmail_info":
        await _safe_answer_query(query)
        await query.message.reply_text(
            "ℹ️ *Gmail Engine is currently offline.*\nTap **Connect Gmail** to authenticate your account.",
            parse_mode="Markdown",
        )
    elif data == "hitl_approve":
        await _safe_answer_query(query)
        await query.edit_message_text(
            "✅ *Action Approved by Operator*\n\n"
            "LocalPilot resumed execution: decrypted credentials injected locally, order simulated successfully.",
            parse_mode="Markdown",
        )
    elif data == "hitl_reject":
        await _safe_answer_query(query)
        await query.edit_message_text(
            "❌ *Action Rejected by Operator*\n\n"
            "LocalPilot aborted operation. No payment was made and no external requests were dispatched.",
            parse_mode="Markdown",
        )
    elif data == "browser_close":
        await _safe_answer_query(query)
        await asyncio.to_thread(browser_service.close_browser)
        await query.edit_message_text(
            "🔒 *Browser closed.* All Playwright resources released.",
            parse_mode="Markdown",
        )
    elif data == "browser_keep":
        await _safe_answer_query(query)
        await query.edit_message_text(
            "🖥️ *Browser kept open.* You can interact with it on your host machine.\n"
            "Send `/close_browser` when you are done.",
            parse_mode="Markdown",
        )
    elif data == "agent_toggle_pause":
        new_state = browser_service.pause_agent()
        status_word = "PAUSED ⏸️" if new_state else "RESUMED ▶️"
        await _safe_answer_query(query, f"Agent {status_word}", show_alert=False)
    elif data == "agent_go_back":
        browser_service.trigger_go_back()
        await _safe_answer_query(query, "Navigating back one step ⬅️", show_alert=False)
    elif data == "agent_stop":
        browser_service.stop_agent()
        await _safe_answer_query(query, "Stopping agent loop 🛑", show_alert=False)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes natural language input sent by the operator."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    user_text = update.message.text.strip()
    user_lower = user_text.lower()
    logger.info(f"Incoming user instruction: {user_text}")

    # Natural language dispatch for email summaries
    if any(keyword in user_lower for keyword in ["email", "summary", "digest", "inbox", "mail"]):
        await summary_handler(update, context)
        return

    # Natural language dispatch for browser tasks: pass the actual user message as the task!
    if any(keyword in user_lower for keyword in ["browse", "browser", "go to", "search", "open", "find", "github", "website", "check"]):
        await call_browser_handler(update, context, custom_task=user_text)
        return

    response = (
        f"🤖 *LocalPilot Core Received:*\n"
        f"> \"_{update.message.text}_\"\n\n"
        f"⚙️ *Pipeline Dispatch:*\n"
        f"• Task queued for intent classification\n"
        f"• Model router: On-device vs. Cloud orchestration\n"
        f"• Execution engine: Ready for Playwright / Gmail REST module\n\n"
        f"_(Send a prompt like 'Go to github.com and find Ollama' to trigger web automation)_"
    )
    await update.message.reply_text(response, parse_mode="Markdown")


async def call_browser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_task: Optional[str] = None) -> None:
    """Launches Playwright browser and uses Ollama Qwen to autonomously navigate and answer."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    # Check if a custom task was passed directly or via command arguments (e.g. /call_browser <prompt>)
    if not custom_task and context and context.args:
        custom_task = " ".join(context.args).strip()

    # Use the user's custom typed message if provided, else fallback to default demo task
    task = custom_task or "Open github.com/ndanevski1 and tell me how many repositories they have and their latest activity."

    loading_msg = (
        "🌐 *Browser Agent Activated*\n\n"
        f"📋 *Task:* _{task}_\n\n"
        "⚙️ *Status:*\n"
        "• Launching visible Chromium browser on host...\n"
        "• Initializing autonomous Qwen navigation loop...\n\n"
        "⏳ _Please watch the browser on your screen as the agent navigates..._"
    )

    if update.callback_query:
        await _safe_answer_query(update.callback_query)
        msg_ref = await update.callback_query.message.reply_text(loading_msg, parse_mode="Markdown")
    else:
        msg_ref = await update.message.reply_text(loading_msg, parse_mode="Markdown")

    loop = asyncio.get_running_loop()

    def handle_step_update(step: int, max_steps: int, action_desc: str, current_url: str):
        """Thread-safe real-time UI updater for Telegram."""
        step_text = (
            f"🌐 *Browser Agent Live Progress*\n\n"
            f"📋 *Task:* _{task}_\n\n"
            f"📊 *Status:* Step {step}/{max_steps}\n"
            f"🤖 *Qwen Decision:* {action_desc}\n"
            f"🔗 *URL:* `{current_url}`\n\n"
            f"⏳ _Live agent loop in progress..._"
        )
        # Live control buttons during execution
        live_controls = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏸️ Pause / Resume", callback_data="agent_toggle_pause"),
                InlineKeyboardButton("⬅️ Go Back", callback_data="agent_go_back"),
            ],
            [
                InlineKeyboardButton("🛑 Stop Agent", callback_data="agent_stop"),
            ]
        ])

        try:
            asyncio.run_coroutine_threadsafe(
                msg_ref.edit_text(step_text, reply_markup=live_controls, parse_mode="Markdown"),
                loop
            )
        except Exception:
            pass

    # Run the blocking browser + Ollama pipeline on a separate thread with the live updater
    success, answer, final_url = await asyncio.to_thread(
        browser_service.browse_and_answer,
        task,
        handle_step_update
    )

    if success:
        # Build HITL buttons for browser control
        keyboard = [
            [
                InlineKeyboardButton("✅ Close Browser", callback_data="browser_close"),
                InlineKeyboardButton("🖥️ Keep Open", callback_data="browser_keep"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        result_text = (
            f"🌐 *Browser Agent Result*\n\n"
            f"📋 *Task:* _{task}_\n\n"
            f"🤖 *Qwen Answer:*\n{answer}\n\n"
            f"🔗 *Final URL:* `{final_url}`\n\n"
            f"_Would you like to close the browser or keep it open for inspection?_"
        )
        await msg_ref.edit_text(result_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await msg_ref.edit_text(
            f"❌ *Browser Task Failed:*\n{answer}\n\n🔗 URL: `{final_url}`",
            parse_mode="Markdown",
        )


async def close_browser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /close_browser command."""
    if not check_auth(update):
        await unauthorized_warning(update)
        return

    if browser_service.is_browser_open():
        await asyncio.to_thread(browser_service.close_browser)
        await update.message.reply_text(
            "🔒 *Browser closed.* All Playwright resources released.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "ℹ️ No browser is currently open.",
            parse_mode="Markdown",
        )


def main() -> None:
    """Initializes and runs the Telegram Bot polling daemon."""
    if not BOT_TOKEN or BOT_TOKEN.startswith("your_"):
        logger.error("Missing or invalid TELEGRAM_BOT_TOKEN in .env file!")
        print("Error: Please specify TELEGRAM_BOT_TOKEN in your .env file.")
        return

    logger.info("Initializing LocalPilot Telegram Bot with Gmail + Browser Engine...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("connect_gmail", connect_gmail_handler))
    app.add_handler(CommandHandler("disconnect_gmail", disconnect_gmail_handler))
    app.add_handler(CommandHandler("demo_hitl", demo_hitl_handler))
    app.add_handler(CommandHandler("call_browser", call_browser_handler))
    app.add_handler(CommandHandler("close_browser", close_browser_handler))

    # Register Callback & Message Handlers
    app.add_handler(CallbackQueryHandler(callback_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    logger.info("LocalPilot Telegram Bot is running (Long-polling active)...")
    logger.info("Press Ctrl+C to terminate the daemon.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
