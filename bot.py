"""
LocalPilot — On-Device Personal Action Agent
Telegram Remote Interface Daemon

Message formatting: every message uses Telegram's HTML parse mode and every
dynamic value is escaped with safety.h(), so user text, URLs, email subjects and
model answers can contain any characters (_ * [ ] ` < > &) without breaking.
"""

import asyncio
import functools
import logging
import os
import platform
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import approval_gate
import browser_service
import gmail_service
from safety import RedactingFormatter, h, redact, truncate

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "localpilot.log")
LOG_FORMAT = "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
logger = logging.getLogger("LocalPilot")

HTML = ParseMode.HTML
DEFAULT_BROWSER_TASK = "Open https://example.com and tell me the page title."

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
APP_ENV = os.getenv("LOCALPILOT_ENV", "development").strip().lower()

SETUP_MODE_WARNING = (
    "SETUP MODE: TELEGRAM_ALLOWED_USER_ID is empty. The bot will only tell users their "
    "Telegram ID and every feature is disabled until you set TELEGRAM_ALLOWED_USER_ID in .env "
    "and restart. Never run with an empty value in production (LOCALPILOT_ENV=production refuses to start)."
)

# One browser task at a time (live controls and approvals share global agent state).
_browser_task_lock = asyncio.Lock()
_background_tasks: set = set()


# --------------------------------------------------------------------------- #
# Logging & configuration
# --------------------------------------------------------------------------- #

def setup_logging() -> None:
    """Logs to console and localpilot.log; secrets are redacted from every line."""
    root = logging.getLogger()
    if getattr(root, "_localpilot_configured", False):
        return
    formatter = RedactingFormatter(LOG_FORMAT)
    for handler in (logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    # httpx logs every request URL, and Telegram API URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    root._localpilot_configured = True


def validate_config(token: str, allowed_user_id: str, app_env: str) -> Tuple[List[str], List[str]]:
    """Returns (errors, warnings). Any error means the bot must not start."""
    errors: List[str] = []
    warnings: List[str] = []
    if not token or token.startswith("your_"):
        errors.append("TELEGRAM_BOT_TOKEN is missing or still set to the placeholder value.")
    if allowed_user_id:
        if not allowed_user_id.isdigit():
            errors.append("TELEGRAM_ALLOWED_USER_ID must be your numeric Telegram user ID.")
    elif app_env == "production":
        errors.append("TELEGRAM_ALLOWED_USER_ID must be set when LOCALPILOT_ENV=production.")
    else:
        warnings.append(SETUP_MODE_WARNING)
    return errors, warnings


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #

def is_setup_mode() -> bool:
    return not ALLOWED_USER_ID


def is_authorized(update: Update) -> bool:
    """True only when an owner ID is configured and the sender matches it."""
    if not ALLOWED_USER_ID:
        return False
    user = update.effective_user
    return bool(user) and str(user.id) == ALLOWED_USER_ID


# Backwards-compatible name used by older code.
check_auth = is_authorized


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


async def unauthorized_warning(update: Update) -> None:
    """Rejects a command, message or button press from anyone but the owner."""
    user = update.effective_user
    logger.warning("Rejected update from unauthorized Telegram user %s", user.id if user else "unknown")
    if update.callback_query:
        await _safe_answer_query(update.callback_query, "⛔ Access denied", show_alert=True)
        return
    if is_setup_mode():
        text = (
            "⚠️ <b>LocalPilot is in setup mode</b>\n"
            "All features are disabled until the owner sets <code>TELEGRAM_ALLOWED_USER_ID</code>. "
            "Send /start to see your Telegram user ID."
        )
    else:
        text = "⛔ <b>Access Denied</b>\nThis LocalPilot instance is locked to a private host machine."
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode=HTML)


def require_auth(func):
    """Decorator: re-checks the sender on every command, message and button press."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not is_authorized(update):
            await unauthorized_warning(update)
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper


async def _reply(update: Update, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Replies with HTML to either a command or a button press."""
    if update.callback_query:
        await _safe_answer_query(update.callback_query)
        return await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=HTML)
    return await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=HTML)


# --------------------------------------------------------------------------- #
# Menu & basic commands
# --------------------------------------------------------------------------- #

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
    """Handles the /start command. In setup mode it only reveals the sender's own ID."""
    user = update.effective_user
    user_id = user.id if user else "Unknown"

    if is_setup_mode():
        text = (
            "⚠️ <b>LocalPilot is in SETUP MODE</b>\n\n"
            "This bot is not locked to an owner yet, so every feature is disabled.\n\n"
            f"• <b>Your Telegram user ID:</b> <code>{h(user_id)}</code>\n\n"
            "To finish setup, add this line to the <code>.env</code> file on the host computer and restart the bot:\n"
            f"<code>TELEGRAM_ALLOWED_USER_ID={h(user_id)}</code>\n\n"
            "<i>If you are not the owner of this bot, you can ignore this message.</i>"
        )
        await _reply(update, text)
        return

    if not is_authorized(update):
        await unauthorized_warning(update)
        return

    first_name = user.first_name if user else "Operator"

    if gmail_service.is_connected():
        email_addr = gmail_service.get_connected_email() or "Authorized Account"
        gmail_status = f"🟢 Connected (<code>{h(email_addr)}</code>)"
    else:
        gmail_status = "⚪ Not Connected (Optional)"

    welcome_text = (
        f"👋 <b>Hello, {h(first_name)}!</b>\n\n"
        "🤖 Welcome to <b>LocalPilot</b> — your on-device personal action agent.\n\n"
        "📋 <b>Session Info:</b>\n"
        f"• <b>Your User ID:</b> <code>{h(user_id)}</code>\n"
        "• <b>Security Gate:</b> 🔒 Locked to your user ID\n"
        f"• <b>Gmail Engine:</b> {gmail_status}\n"
        "\nSelect an option below or send an instruction to test the agent:"
    )
    await _reply(update, welcome_text, build_menu_markup())


@require_auth
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /status command."""
    node = platform.node()
    system = f"{platform.system()} {platform.release()}"
    python_ver = platform.python_version()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if gmail_service.is_connected():
        email_addr = gmail_service.get_connected_email() or "Google User"
        gmail_status = f"🟢 Connected (<code>{h(email_addr)}</code>)"
    else:
        gmail_status = "⚪ Disconnected (Run <code>/connect_gmail</code>)"

    status_message = (
        "📊 <b>LocalPilot Host Status</b>\n\n"
        "• <b>Status:</b> 🟢 Online &amp; Listening\n"
        f"• <b>Host Node:</b> <code>{h(node)}</code>\n"
        f"• <b>OS Platform:</b> <code>{h(system)}</code>\n"
        f"• <b>Python Core:</b> <code>v{h(python_ver)}</code>\n"
        f"• <b>Host Time:</b> <code>{h(now_str)}</code>\n"
        f"• <b>Gmail Engine:</b> {gmail_status}\n"
        "• <b>Outbound Link:</b> Secure Polling (No open ports)"
    )
    await _reply(update, status_message)


@require_auth
async def connect_gmail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explains how to run the one-time Google OAuth 2.0 flow on the host."""
    if gmail_service.is_connected():
        email = gmail_service.get_connected_email() or "authenticated user"
        msg = (
            f"✅ Gmail is already connected as <code>{h(email)}</code>.\n"
            "Use <code>/summary</code> to fetch unread emails or <code>/disconnect_gmail</code> to opt out."
        )
        await _reply(update, msg)
        return

    prompt_msg = (
        "🌐 <b>Connect Gmail via Google OAuth 2.0 (read-only)</b>\n\n"
        "The bot runs in the background, so it cannot open the Google sign-in window itself.\n\n"
        "💻 <b>To connect:</b>\n"
        "1. Open a terminal in the project folder on the host computer\n"
        "2. Run:\n"
        "   <code>python setup_gmail.py</code>\n"
        "3. Your browser opens. Choose your account and grant <b>read-only</b> access.\n\n"
        "Once complete, tap <code>/start</code> or send <code>/summary</code> to test your inbox digest."
    )
    await _reply(update, prompt_msg)


@require_auth
async def disconnect_gmail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the local Gmail token and explains how to revoke the Google grant."""
    _success, message = await asyncio.to_thread(gmail_service.disconnect)
    resp = (
        f"🔌 <b>Gmail Status:</b> {h(message)}\n\n"
        f"ℹ️ {h(gmail_service.REVOKE_NOTE)}"
    )
    await _reply(update, resp, build_menu_markup())


@require_auth
async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays an email digest of unread primary inbox messages."""
    if not gmail_service.is_connected():
        resp = (
            "📭 <b>Gmail is not connected</b>\n\n"
            "To enable inbox summaries, tap <b>Connect Gmail</b> or send <code>/connect_gmail</code>."
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Connect Gmail Now", callback_data="connect_gmail")]])
        await _reply(update, resp, markup)
        return

    msg_ref = await _reply(update, "🔍 <b>Scanning unread emails in your primary inbox...</b>")

    success, emails, info = await asyncio.to_thread(gmail_service.get_unread_emails, 5)
    if not success:
        await msg_ref.edit_text(f"❌ <b>Failed to retrieve emails:</b>\n{h(info)}", parse_mode=HTML)
        return

    # The digest goes to Telegram only; email content is never logged.
    logger.info("Email digest delivered (%d messages).", len(emails))
    await msg_ref.edit_text(gmail_service.format_email_digest(emails), parse_mode=HTML)


@require_auth
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /help command."""
    help_text = (
        "📖 <b>LocalPilot Command Reference</b>\n\n"
        "• <code>/start</code> - Launch or refresh the main interactive menu\n"
        "• <code>/status</code> - Check host connectivity, system health &amp; Gmail status\n"
        "• <code>/summary</code> - Fetch and summarize latest unread emails\n"
        "• <code>/connect_gmail</code> - Connect your Google account (read-only) via OAuth 2.0\n"
        "• <code>/disconnect_gmail</code> - Delete the local Google token on this computer\n"
        "• <code>/call_browser</code> - Run a browser task (e.g. <code>/call_browser open example.com</code>)\n"
        "• <code>/close_browser</code> - Close the agent's browser window\n"
        "• <code>/demo_hitl</code> - Simulated Human-in-the-Loop approval (nothing is bought)\n"
        "• <code>/help</code> - View this reference card\n\n"
        "💬 <b>Action Prompts:</b>\n"
        "You can also send natural language text like <i>\"Give me an email summary\"</i> or "
        "<i>\"Open example.com and tell me the page title\"</i> directly in this chat."
    )
    await _reply(update, help_text)


# --------------------------------------------------------------------------- #
# Human-in-the-Loop approvals
# --------------------------------------------------------------------------- #

DEMO_ACTION: Dict[str, Any] = {
    "simulation": True,
    "operation": "Place web order",
    "site": "demo-shop.example",
    "item": "USB-C cable, 2-pack (fictional item)",
    "amount": "14.99",
    "currency": "USD",
}


def approval_markup(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve Action", callback_data=f"hitl:approve:{request_id}"),
        InlineKeyboardButton("❌ Reject / Abort", callback_data=f"hitl:reject:{request_id}"),
    ]])


def _expiry_text(req: approval_gate.ApprovalRequest) -> str:
    return datetime.fromtimestamp(req.expires_at).strftime("%H:%M")


def demo_card_text(req: approval_gate.ApprovalRequest) -> str:
    a = req.action
    return (
        "⚠️ <b>Human-in-the-Loop Approval — SIMULATION</b>\n"
        "<i>(Demo of SRS Module 3. Nothing will be bought and no credentials are used.)</i>\n\n"
        "An example state-changing action is waiting for your decision:\n\n"
        f"• <b>Operation:</b> {h(a['operation'])}\n"
        f"• <b>Vendor:</b> {h(a['site'])}\n"
        f"• <b>Item:</b> {h(a['item'])}\n"
        f"• <b>Price:</b> <code>${h(a['amount'])}</code> (fictional)\n"
        f"• <b>Request ID:</b> <code>{h(req.request_id)}</code>\n"
        f"• <b>Expires at:</b> {h(_expiry_text(req))} (30 minutes)\n\n"
        "Please confirm or cancel this action:"
    )


def browser_approval_card_text(req: approval_gate.ApprovalRequest) -> str:
    a = req.action
    kind = "Type text into a form field" if a.get("kind") == "type" else "Click a page element"
    lines = [
        "🛡️ <b>Approval needed: state-changing browser action</b>",
        "",
        "The browser agent paused before doing this:",
        "",
        f"• <b>Action:</b> {h(kind)}",
        f"• <b>Website:</b> <code>{h(a.get('site'))}</code>",
        f"• <b>Page:</b> <code>{h(truncate(a.get('url'), 200))}</code>",
        f"• <b>Target:</b> {h(truncate(a.get('target_label'), 100))} (&lt;{h(a.get('target_tag'))}&gt;)",
    ]
    if a.get("kind") == "type":
        lines.append(f"• <b>Text:</b> <code>{h(truncate(redact(a.get('text')), 200))}</code>")
        lines.append(f"• <b>Press Enter afterwards:</b> {'yes' if a.get('press_enter') else 'no'}")
    if a.get("purchase"):
        lines.append(f"• <b>Amount (reported by the model, check the page):</b> <code>{h(a.get('amount'))} {h(a.get('currency') or '')}</code>")
    lines += [
        "",
        f"• <b>Request ID:</b> <code>{h(req.request_id)}</code>",
        f"• <b>Expires at:</b> {h(_expiry_text(req))} (30 minutes)",
        "",
        "Approve only if this is exactly what you want. The approval works once, for this exact action.",
    ]
    return "\n".join(lines)


def decision_text(req: approval_gate.ApprovalRequest) -> str:
    """Final card text after a decision, expiry or cancellation."""
    status = req.status
    sim = bool(req.action.get("simulation"))
    S = approval_gate.ApprovalStatus
    if status == S.APPROVED and sim:
        return (
            "✅ <b>Approved (simulation)</b>\n\n"
            f"Your approval for request <code>{h(req.request_id)}</code> was recorded once and cannot be reused.\n"
            "This was a demo: no order was placed, no payment was made and no credentials were used."
        )
    if status == S.APPROVED:
        return (
            "✅ <b>Approved</b>\n\n"
            f"LocalPilot will perform this one action on <code>{h(req.action.get('site'))}</code>, "
            "provided the page has not changed since you approved it."
        )
    if status == S.REJECTED:
        if sim:
            return "❌ <b>Rejected (simulation)</b>\n\nNothing was done. No order was placed and no payment was made."
        return "❌ <b>Rejected</b>\n\nThe action was not performed and the browser task was stopped."
    if status == S.EXPIRED:
        return "⌛ <b>Approval expired</b>\n\nNo decision was made within 30 minutes, so the action was cancelled."
    if status == S.CANCELLED:
        return "🛑 <b>Approval cancelled</b>\n\nThe action was not performed."
    return "⏳ <b>Approval pending</b>"


async def _expire_after_deadline(request_id: str, message) -> None:
    """Edits the approval card to 'expired' if nobody decided in time."""
    gate = approval_gate.GATE
    req = gate.get(request_id)
    if req is None:
        return
    await asyncio.sleep(max(0.0, req.expires_at - time.time()))
    if gate.expire_if_pending(request_id):
        logger.info("Approval request %s expired; action cancelled.", request_id)
        try:
            await message.edit_text(decision_text(gate.get(request_id)), parse_mode=HTML)
        except Exception as e:
            logger.warning("Could not edit expired approval card: %s", type(e).__name__)


def _start_expiry_watch(request_id: str, message) -> None:
    task = asyncio.create_task(_expire_after_deadline(request_id, message))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@require_auth
async def demo_hitl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simulated HITL approval that uses the real approval gate (tracking, expiry, replay protection)."""
    req = approval_gate.GATE.create(update.effective_user.id, DEMO_ACTION)
    msg = await _reply(update, demo_card_text(req), approval_markup(req.request_id))
    _start_expiry_watch(req.request_id, msg)


async def _handle_hitl_decision(update: Update, data: str) -> None:
    query = update.callback_query
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[1] not in ("approve", "reject") or not parts[2]:
        await _safe_answer_query(query, "This approval card is no longer valid.", show_alert=True)
        return
    _, verb, request_id = parts
    gate = approval_gate.GATE
    accepted, reason = gate.decide(request_id, update.effective_user.id, approve=(verb == "approve"))
    req = gate.get(request_id)
    if not accepted:
        await _safe_answer_query(query, reason, show_alert=True)
        if req is not None and req.status == approval_gate.ApprovalStatus.EXPIRED:
            await query.edit_message_text(decision_text(req), parse_mode=HTML)
        return
    logger.info("Approval request %s %s by owner.", request_id, req.status.value)
    await _safe_answer_query(query)
    await query.edit_message_text(decision_text(req), parse_mode=HTML)


# --------------------------------------------------------------------------- #
# Button presses
# --------------------------------------------------------------------------- #

async def callback_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes interactive button presses. The presser is re-authenticated first."""
    query = update.callback_query
    if not query:
        return
    if not is_authorized(update):
        await unauthorized_warning(update)
        return

    data = query.data or ""
    if data.startswith("hitl:"):
        await _handle_hitl_decision(update, data)
    elif data in ("hitl_approve", "hitl_reject"):
        # Cards created before approval tracking existed carry no request ID.
        await _safe_answer_query(query, "This approval card is outdated. Send /demo_hitl for a new one.", show_alert=True)
    elif data == "status":
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
        await _reply(update, "ℹ️ <b>Gmail Engine is currently offline.</b>\nTap <b>Connect Gmail</b> to authenticate your account.")
    elif data == "browser_close":
        await _safe_answer_query(query)
        await browser_service.run_in_browser_thread(browser_service.close_browser)
        await query.edit_message_text("🔒 <b>Browser closed.</b> All Playwright resources released.", parse_mode=HTML)
    elif data == "browser_keep":
        await _safe_answer_query(query)
        await query.edit_message_text(
            "🖥️ <b>Browser kept open.</b> You can interact with it on your host machine.\n"
            "Send <code>/close_browser</code> when you are done.",
            parse_mode=HTML,
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
    else:
        await _safe_answer_query(query)


# --------------------------------------------------------------------------- #
# Natural language & browser
# --------------------------------------------------------------------------- #

@require_auth
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes natural language input sent by the operator."""
    user_text = (update.message.text or "").strip()
    user_lower = user_text.lower()
    logger.info("Incoming user instruction (%d chars): %s", len(user_text), truncate(redact(user_text), 120))

    # Natural language dispatch for email summaries
    if any(keyword in user_lower for keyword in ["email", "summary", "digest", "inbox", "mail"]):
        await summary_handler(update, context)
        return

    # Natural language dispatch for browser tasks: pass the actual user message as the task!
    if any(keyword in user_lower for keyword in ["browse", "browser", "go to", "search", "open", "find", "github", "website", "check"]):
        await call_browser_handler(update, context, custom_task=user_text)
        return

    response = (
        "🤖 <b>LocalPilot received:</b>\n"
        f"<i>{h(truncate(user_text, 500))}</i>\n\n"
        "I couldn't match this to a feature yet. Right now I can:\n"
        "• Summarize unread email: mention <i>email</i>, <i>inbox</i> or <i>summary</i>\n"
        "• Browse the web: mention <i>open</i>, <i>search</i>, <i>go to</i> or a website\n\n"
        "<i>(Example: \"Open https://example.com and tell me the page title\")</i>"
    )
    await update.message.reply_text(response, parse_mode=HTML)


async def _send_approval_card(msg_ref, req: approval_gate.ApprovalRequest) -> None:
    card = await msg_ref.reply_text(browser_approval_card_text(req), reply_markup=approval_markup(req.request_id), parse_mode=HTML)
    _start_expiry_watch(req.request_id, card)


@require_auth
async def call_browser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_task: Optional[str] = None) -> None:
    """Launches Playwright browser and uses Ollama Qwen to autonomously navigate and answer."""
    # Check if a custom task was passed directly or via command arguments (e.g. /call_browser <prompt>)
    if not custom_task and context is not None and getattr(context, "args", None):
        custom_task = " ".join(context.args).strip()

    task = custom_task or DEFAULT_BROWSER_TASK

    if _browser_task_lock.locked():
        await _reply(update, "⏳ A browser task is already running. Wait for it to finish or press 🛑 Stop Agent.")
        return

    async with _browser_task_lock:
        loading_msg = (
            "🌐 <b>Browser Agent Activated</b>\n\n"
            f"📋 <b>Task:</b> <i>{h(truncate(task, 500))}</i>\n\n"
            "⚙️ <b>Status:</b>\n"
            "• Launching visible Chromium browser on host...\n"
            "• Initializing autonomous Qwen navigation loop...\n\n"
            "⏳ <i>Please watch the browser on your screen as the agent navigates...</i>"
        )
        msg_ref = await _reply(update, loading_msg)

        loop = asyncio.get_running_loop()
        owner_id = update.effective_user.id

        def handle_step_update(step: int, max_steps: int, action_desc: str, current_url: str):
            """Thread-safe real-time UI updater for Telegram."""
            step_text = (
                "🌐 <b>Browser Agent Live Progress</b>\n\n"
                f"📋 <b>Task:</b> <i>{h(truncate(task, 500))}</i>\n\n"
                f"📊 <b>Status:</b> Step {step}/{max_steps}\n"
                f"🤖 <b>Qwen Decision:</b> {h(truncate(action_desc, 500))}\n"
                f"🔗 <b>URL:</b> <code>{h(truncate(current_url, 300))}</code>\n\n"
                "⏳ <i>Live agent loop in progress...</i>"
            )
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
                    msg_ref.edit_text(step_text, reply_markup=live_controls, parse_mode=HTML),
                    loop
                )
            except Exception:
                pass

        def request_approval(details: Dict[str, Any]):
            """Called from the agent thread for each state-changing action that passed policy checks."""
            gate = approval_gate.GATE
            req = gate.create(owner_id, details)
            future = asyncio.run_coroutine_threadsafe(_send_approval_card(msg_ref, req), loop)
            try:
                future.result(timeout=30)
            except Exception as e:
                logger.warning("Could not deliver approval card (%s); cancelling action.", type(e).__name__)
                gate.cancel(req.request_id)
                return approval_gate.ApprovalStatus.CANCELLED, req.request_id
            status = gate.wait(req.request_id, should_abort=browser_service.is_stop_requested)
            return status, req.request_id

        # Run the blocking browser + Ollama pipeline on the dedicated Playwright thread with the live updater
        success, answer, final_url = await browser_service.run_in_browser_thread(
            browser_service.browse_and_answer,
            task,
            handle_step_update,
            request_approval,
        )

        if success:
            keyboard = [[
                InlineKeyboardButton("✅ Close Browser", callback_data="browser_close"),
                InlineKeyboardButton("🖥️ Keep Open", callback_data="browser_keep"),
            ]]
            result_text = (
                "🌐 <b>Browser Agent Result</b>\n\n"
                f"📋 <b>Task:</b> <i>{h(truncate(task, 500))}</i>\n\n"
                f"🤖 <b>Qwen Answer:</b>\n{h(truncate(answer, 2500))}\n\n"
                f"🔗 <b>Final URL:</b> <code>{h(truncate(final_url, 300))}</code>\n\n"
                "<i>Would you like to close the browser or keep it open for inspection?</i>"
            )
            await msg_ref.edit_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=HTML)
        else:
            await msg_ref.edit_text(
                f"❌ <b>Browser Task Failed:</b>\n{h(truncate(answer, 2500))}\n\n🔗 URL: <code>{h(truncate(final_url, 300))}</code>",
                parse_mode=HTML,
            )


@require_auth
async def close_browser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /close_browser command."""
    if browser_service.is_browser_open():
        await browser_service.run_in_browser_thread(browser_service.close_browser)
        await _reply(update, "🔒 <b>Browser closed.</b> All Playwright resources released.")
    else:
        await _reply(update, "ℹ️ No browser is currently open.")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def build_application(token: str):
    # concurrent_updates: live controls (Pause/Stop) and Approve/Reject must be
    # processed while a browser task is still running.
    app = ApplicationBuilder().token(token).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("connect_gmail", connect_gmail_handler))
    app.add_handler(CommandHandler("disconnect_gmail", disconnect_gmail_handler))
    app.add_handler(CommandHandler("demo_hitl", demo_hitl_handler))
    app.add_handler(CommandHandler("call_browser", call_browser_handler))
    app.add_handler(CommandHandler("close_browser", close_browser_handler))

    app.add_handler(CallbackQueryHandler(callback_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    return app


def main() -> int:
    """Validates configuration, then runs the Telegram Bot polling daemon."""
    setup_logging()
    errors, warnings = validate_config(BOT_TOKEN, ALLOWED_USER_ID, APP_ENV)
    for warning in warnings:
        logger.warning("!" * 20 + " " + warning + " " + "!" * 20)
    if errors:
        for error in errors:
            logger.error("Configuration error: %s", error)
        print("LocalPilot did not start. Fix the configuration errors above in your .env file.")
        return 1

    logger.info("Initializing LocalPilot Telegram Bot with Gmail + Browser Engine...")
    app = build_application(BOT_TOKEN)
    logger.info("LocalPilot Telegram Bot is running (Long-polling active)...")
    logger.info("Press Ctrl+C to terminate the daemon.")
    app.run_polling(drop_pending_updates=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
