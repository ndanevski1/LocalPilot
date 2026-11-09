"""
Tests for bot.py. Telegram objects are replaced by mocks; Gmail and the browser
are mocked too, so no network, Google account or browser is used.
"""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import approval_gate
import bot

OWNER = 111111
STRANGER = 999999

NASTY = "snake_case_name *star* [bracket](x) `tick` <tag> & https://ex_ample.com/a_b?q=*x*&y=[1]"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class TelegramHTMLChecker(HTMLParser):
    """Validates text the way Telegram's HTML parse mode does (subset of tags, balanced, escaped)."""

    ALLOWED = frozenset({"b", "strong", "i", "em", "u", "s", "code", "pre", "a", "blockquote"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED:
            raise AssertionError(f"Tag <{tag}> is not supported by Telegram")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise AssertionError(f"Unbalanced </{tag}>")

    def handle_data(self, data):
        self.text.append(data)


def assert_telegram_html(test: unittest.TestCase, text: str) -> str:
    """Asserts ``text`` is valid Telegram HTML and returns the visible plain text."""
    bare_amp = re.search(r"&(?!(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)", text)
    test.assertIsNone(bare_amp, f"Unescaped & in: {text!r}")
    checker = TelegramHTMLChecker()
    checker.feed(text)
    checker.close()
    test.assertEqual(checker.stack, [], f"Unclosed tags in: {text!r}")
    return "".join(checker.text)


def make_message(text="hello"):
    sent = MagicMock()
    sent.edit_text = AsyncMock()
    sent.reply_text = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock(return_value=sent)
    return message


def make_update(user_id=OWNER, text="hello", callback_data=None):
    user = SimpleNamespace(id=user_id, first_name="Test_User*")
    message = make_message(text)
    if callback_data is not None:
        query = SimpleNamespace(
            data=callback_data,
            answer=AsyncMock(),
            message=message,
            edit_message_text=AsyncMock(),
            from_user=user,
        )
        return SimpleNamespace(effective_user=user, callback_query=query, message=None, effective_message=message)
    return SimpleNamespace(effective_user=user, callback_query=None, message=message, effective_message=message)


def sent_texts(update) -> list:
    msg = update.effective_message
    texts = [c.args[0] if c.args else c.kwargs.get("text") for c in msg.reply_text.call_args_list]
    return texts


def run(coro):
    return asyncio.run(coro)


class BotTestCase(unittest.TestCase):
    def setUp(self):
        patches = [
            patch.object(bot, "ALLOWED_USER_ID", str(OWNER)),
            patch.object(bot.gmail_service, "is_connected", return_value=False),
            patch.object(bot.gmail_service, "get_connected_email", return_value=None),
            patch.object(bot.approval_gate, "GATE", approval_gate.ApprovalGate()),
            patch.object(bot, "_start_expiry_watch", MagicMock()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


# --------------------------------------------------------------------------- #
# Import & startup
# --------------------------------------------------------------------------- #

class ImportAndStartupTests(unittest.TestCase):
    def test_module_imports_and_exposes_handlers(self):
        for name in ("main", "start_handler", "status_handler", "callback_button_handler",
                     "call_browser_handler", "demo_hitl_handler", "validate_config"):
            self.assertTrue(callable(getattr(bot, name)), name)
        self.assertTrue(hasattr(bot, "Optional"))

    def test_default_browser_task_is_neutral(self):
        self.assertEqual(bot.DEFAULT_BROWSER_TASK, "Open https://example.com and tell me the page title.")
        with open(bot.__file__, encoding="utf-8") as f:
            self.assertNotIn("ndanevski1", f.read())

    def test_valid_config(self):
        self.assertEqual(bot.validate_config("123:abc", "42", "production"), ([], []))

    def test_missing_or_placeholder_token(self):
        for token in ("", "your_bot_token_here"):
            errors, _ = bot.validate_config(token, "42", "development")
            self.assertTrue(errors)

    def test_non_numeric_user_id(self):
        errors, _ = bot.validate_config("123:abc", "your_telegram_numeric_user_id", "development")
        self.assertTrue(any("numeric" in e for e in errors))

    def test_empty_user_id_refused_in_production(self):
        errors, _ = bot.validate_config("123:abc", "", "production")
        self.assertTrue(any("production" in e for e in errors))

    def test_empty_user_id_warns_in_development(self):
        errors, warnings = bot.validate_config("123:abc", "", "development")
        self.assertEqual(errors, [])
        self.assertTrue(any("SETUP MODE" in w for w in warnings))

    def test_main_refuses_to_start_with_bad_config(self):
        with patch.object(bot, "setup_logging"), \
             patch.object(bot, "BOT_TOKEN", ""), \
             patch.object(bot, "build_application") as build:
            self.assertEqual(bot.main(), 1)
            build.assert_not_called()

    def test_main_starts_with_good_config(self):
        app = MagicMock()
        with patch.object(bot, "setup_logging"), \
             patch.object(bot, "BOT_TOKEN", "123:abc"), \
             patch.object(bot, "ALLOWED_USER_ID", "42"), \
             patch.object(bot, "build_application", return_value=app):
            self.assertEqual(bot.main(), 0)
            app.run_polling.assert_called_once()

    def test_build_application_registers_handlers(self):
        app = bot.build_application("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
        self.assertGreaterEqual(sum(len(v) for v in app.handlers.values()), 11)


# --------------------------------------------------------------------------- #
# Authorization: commands
# --------------------------------------------------------------------------- #

class CommandAuthTests(BotTestCase):
    def test_authorized_commands_respond(self):
        for handler in (bot.start_handler, bot.status_handler, bot.help_handler,
                        bot.connect_gmail_handler, bot.summary_handler):
            update = make_update(OWNER)
            run(handler(update, MagicMock(args=[])))
            texts = sent_texts(update)
            self.assertTrue(texts, handler.__name__)
            self.assertNotIn("Access Denied", texts[0], handler.__name__)
            assert_telegram_html(self, texts[0])

    def test_unauthorized_commands_are_denied(self):
        handlers = (bot.start_handler, bot.status_handler, bot.help_handler, bot.summary_handler,
                    bot.connect_gmail_handler, bot.disconnect_gmail_handler, bot.demo_hitl_handler,
                    bot.call_browser_handler, bot.close_browser_handler, bot.message_handler)
        with patch.object(bot.gmail_service, "disconnect") as disconnect, \
             patch.object(bot.browser_service, "browse_and_answer") as browse, \
             patch.object(bot.browser_service, "close_browser") as close:
            for handler in handlers:
                update = make_update(STRANGER, text="open example.com")
                run(handler(update, MagicMock(args=[])))
                texts = sent_texts(update)
                self.assertEqual(len(texts), 1, handler.__name__)
                self.assertIn("Access Denied", texts[0], handler.__name__)
            disconnect.assert_not_called()
            browse.assert_not_called()
            close.assert_not_called()
        self.assertEqual(bot.approval_gate.GATE._requests, {})

    def test_setup_mode_only_reveals_own_id(self):
        with patch.object(bot, "ALLOWED_USER_ID", ""):
            update = make_update(STRANGER)
            run(bot.start_handler(update, MagicMock()))
            text = sent_texts(update)[0]
            self.assertIn("SETUP MODE", text)
            self.assertIn(str(STRANGER), text)
            assert_telegram_html(self, text)
            update.message.reply_text.assert_called_once()
            self.assertIsNone(update.message.reply_text.call_args.kwargs.get("reply_markup"))

            # Every other feature is disabled for everyone, including the would-be owner.
            for handler in (bot.status_handler, bot.demo_hitl_handler, bot.message_handler):
                update = make_update(OWNER)
                run(handler(update, MagicMock()))
                self.assertIn("setup mode", sent_texts(update)[0])

    def test_is_authorized(self):
        self.assertTrue(bot.is_authorized(make_update(OWNER)))
        self.assertFalse(bot.is_authorized(make_update(STRANGER)))
        self.assertFalse(bot.is_authorized(SimpleNamespace(effective_user=None)))
        with patch.object(bot, "ALLOWED_USER_ID", ""):
            self.assertFalse(bot.is_authorized(make_update(OWNER)))


# --------------------------------------------------------------------------- #
# Authorization: callbacks (button presses)
# --------------------------------------------------------------------------- #

class CallbackAuthTests(BotTestCase):
    BUTTONS = ("status", "hitl:approve:abc", "hitl:reject:abc", "agent_toggle_pause", "agent_go_back",
               "agent_stop", "browser_close", "browser_keep", "connect_gmail", "disconnect_gmail",
               "summary", "call_browser", "demo_hitl", "help", "gmail_info")

    def test_unauthorized_callbacks_do_nothing(self):
        with patch.object(bot.browser_service, "pause_agent") as pause, \
             patch.object(bot.browser_service, "trigger_go_back") as back, \
             patch.object(bot.browser_service, "stop_agent") as stop, \
             patch.object(bot.browser_service, "close_browser") as close, \
             patch.object(bot.browser_service, "browse_and_answer") as browse, \
             patch.object(bot.gmail_service, "disconnect") as disconnect:
            for data in self.BUTTONS:
                update = make_update(STRANGER, callback_data=data)
                run(bot.callback_button_handler(update, MagicMock(args=[])))
                q = update.callback_query
                q.answer.assert_called_once_with(text="⛔ Access denied", show_alert=True)
                q.edit_message_text.assert_not_called()
                q.message.reply_text.assert_not_called()
            for m in (pause, back, stop, close, browse, disconnect):
                m.assert_not_called()

    def test_unauthorized_user_cannot_approve_a_real_request(self):
        req = bot.approval_gate.GATE.create(OWNER, {"kind": "click"})
        update = make_update(STRANGER, callback_data=f"hitl:approve:{req.request_id}")
        run(bot.callback_button_handler(update, MagicMock()))
        self.assertEqual(req.status, approval_gate.ApprovalStatus.PENDING)
        self.assertFalse(req.used)

    def test_authorized_callbacks_work(self):
        with patch.object(bot.browser_service, "pause_agent", return_value=True) as pause, \
             patch.object(bot.browser_service, "stop_agent") as stop, \
             patch.object(bot.browser_service, "close_browser") as close:
            for data, mock in (("agent_toggle_pause", pause), ("agent_stop", stop), ("browser_close", close)):
                update = make_update(OWNER, callback_data=data)
                run(bot.callback_button_handler(update, MagicMock()))
                mock.assert_called_once()
        update = make_update(OWNER, callback_data="help")
        run(bot.callback_button_handler(update, MagicMock()))
        assert_telegram_html(self, sent_texts(update)[0])

    def test_outdated_hitl_buttons_are_refused(self):
        update = make_update(OWNER, callback_data="hitl_approve")
        run(bot.callback_button_handler(update, MagicMock()))
        update.callback_query.edit_message_text.assert_not_called()
        self.assertIn("outdated", update.callback_query.answer.call_args.kwargs["text"])


# --------------------------------------------------------------------------- #
# System Status with Gmail disconnected
# --------------------------------------------------------------------------- #

class StatusTests(BotTestCase):
    def check_status_text(self, text):
        self.assertIn("<code>/connect_gmail</code>", text)
        visible = assert_telegram_html(self, text)
        self.assertIn("Disconnected (Run /connect_gmail)", visible)

    def test_status_command_with_gmail_disconnected(self):
        update = make_update(OWNER, text="/status")
        run(bot.status_handler(update, MagicMock()))
        call = update.message.reply_text.call_args
        self.assertEqual(call.kwargs["parse_mode"], bot.HTML)
        self.check_status_text(call.args[0])

    def test_status_button_with_gmail_disconnected(self):
        update = make_update(OWNER, callback_data="status")
        run(bot.callback_button_handler(update, MagicMock()))
        update.callback_query.answer.assert_called_once()
        call = update.callback_query.message.reply_text.call_args
        self.assertEqual(call.kwargs["parse_mode"], bot.HTML)
        self.check_status_text(call.args[0])

    def test_status_with_special_characters_in_host_name(self):
        with patch.object(bot.platform, "node", return_value="my_host*[1]`<x>&"):
            update = make_update(OWNER)
            run(bot.status_handler(update, MagicMock()))
        visible = assert_telegram_html(self, sent_texts(update)[0])
        self.assertIn("my_host*[1]`<x>&", visible)


# --------------------------------------------------------------------------- #
# Special characters in dynamic text
# --------------------------------------------------------------------------- #

class SpecialCharacterTests(BotTestCase):
    def test_email_digest_with_markdown_characters(self):
        emails = [{"id": "1", "sender": "Bob_Smith <bob_smith@ex_ample.com>", "subject": NASTY, "snippet": NASTY, "date": ""}]
        text = bot.gmail_service.format_email_digest(emails)
        visible = assert_telegram_html(self, text)
        self.assertIn(NASTY, visible)
        self.assertIn("Bob_Smith <bob_smith@ex_ample.com>", visible)

    def test_summary_handler_sends_escaped_digest(self):
        emails = [{"id": "1", "sender": "a_b", "subject": NASTY, "snippet": "x", "date": ""}]
        with patch.object(bot.gmail_service, "is_connected", return_value=True), \
             patch.object(bot.gmail_service, "get_unread_emails", return_value=(True, emails, "ok")):
            update = make_update(OWNER)
            run(bot.summary_handler(update, MagicMock()))
        sent = update.message.reply_text.return_value
        digest = sent.edit_text.call_args.args[0]
        self.assertIn(NASTY, assert_telegram_html(self, digest))

    def test_unrecognized_message_echo(self):
        text = "hello _x_ *y* [z](w) `v` <q> & https://a_b.example/p_q?r=*s*"
        update = make_update(OWNER, text=text)
        run(bot.message_handler(update, MagicMock()))
        visible = assert_telegram_html(self, sent_texts(update)[0])
        self.assertIn(text, visible)
        self.assertNotIn("Cloud", visible)  # no claims about unimplemented model routing

    def test_browser_result_and_task_with_special_characters(self):
        with patch.object(bot.browser_service, "browse_and_answer", return_value=(True, NASTY, "https://ex.com/a_b?c=*d*")):
            update = make_update(OWNER)
            run(bot.call_browser_handler(update, MagicMock(args=[]), custom_task=NASTY))
        loading = update.message.reply_text.call_args.args[0]
        self.assertIn(NASTY, assert_telegram_html(self, loading))
        result = update.message.reply_text.return_value.edit_text.call_args.args[0]
        visible = assert_telegram_html(self, result)
        self.assertIn(NASTY, visible)
        self.assertIn("https://ex.com/a_b?c=*d*", visible)

    def test_browser_failure_with_special_characters(self):
        with patch.object(bot.browser_service, "browse_and_answer", return_value=(False, "Err_or *x* `y`", "N/A")):
            update = make_update(OWNER)
            run(bot.call_browser_handler(update, MagicMock(args=[])))
        result = update.message.reply_text.return_value.edit_text.call_args.args[0]
        self.assertIn("Err_or *x* `y`", assert_telegram_html(self, result))

    def test_default_browser_task_used(self):
        with patch.object(bot.browser_service, "browse_and_answer", return_value=(True, "Example Domain", "https://example.com")) as browse:
            run(bot.call_browser_handler(make_update(OWNER), MagicMock(args=[])))
        self.assertEqual(browse.call_args.args[0], bot.DEFAULT_BROWSER_TASK)

    def test_long_answers_are_truncated(self):
        with patch.object(bot.browser_service, "browse_and_answer", return_value=(True, "x" * 10000, "https://e.com")):
            update = make_update(OWNER)
            run(bot.call_browser_handler(update, MagicMock(args=[])))
        result = update.message.reply_text.return_value.edit_text.call_args.args[0]
        self.assertLess(len(result), 4096)

    def test_browser_approval_card_with_special_characters(self):
        req = bot.approval_gate.GATE.create(OWNER, {
            "kind": "type", "site": "shop_x.example", "url": "https://shop_x.example/a?b=*c*",
            "target_label": NASTY, "target_tag": "input", "text": "note *x* password: hunter2", "press_enter": True,
            "purchase": True, "amount": "9.99", "currency": "USD",
        })
        visible = assert_telegram_html(self, bot.browser_approval_card_text(req))
        self.assertIn(NASTY, visible)
        self.assertNotIn("hunter2", visible)

    def test_disconnect_gmail_explains_revocation(self):
        with patch.object(bot.gmail_service, "disconnect", return_value=(True, "done_ok")):
            update = make_update(OWNER)
            run(bot.disconnect_gmail_handler(update, MagicMock()))
        visible = assert_telegram_html(self, sent_texts(update)[0])
        self.assertIn("does not necessarily revoke", visible)
        self.assertIn("myaccount.google.com/permissions", visible)


# --------------------------------------------------------------------------- #
# HITL demo through the real approval gate
# --------------------------------------------------------------------------- #

class HitlDemoTests(BotTestCase):
    def create_demo(self):
        update = make_update(OWNER)
        run(bot.demo_hitl_handler(update, MagicMock()))
        gate = bot.approval_gate.GATE
        (req,) = gate._requests.values()
        card = sent_texts(update)[0]
        return req, card, update

    def press(self, data, user=OWNER):
        update = make_update(user, callback_data=data)
        run(bot.callback_button_handler(update, MagicMock()))
        return update.callback_query

    def test_demo_is_labelled_as_simulation(self):
        req, card, update = self.create_demo()
        visible = assert_telegram_html(self, card)
        self.assertIn("SIMULATION", visible)
        self.assertIn(req.request_id, visible)
        self.assertEqual(req.user_id, OWNER)
        markup = update.message.reply_text.call_args.kwargs["reply_markup"]
        datas = [b.callback_data for b in markup.inline_keyboard[0]]
        self.assertEqual(datas, [f"hitl:approve:{req.request_id}", f"hitl:reject:{req.request_id}"])
        bot._start_expiry_watch.assert_called_once()

    def test_approve_once_and_no_false_claims(self):
        req, _, _ = self.create_demo()
        q = self.press(f"hitl:approve:{req.request_id}")
        text = q.edit_message_text.call_args.args[0]
        visible = assert_telegram_html(self, text)
        self.assertIn("Approved (simulation)", visible)
        self.assertIn("no order was placed", visible)
        self.assertNotIn("injected", visible.lower())
        self.assertNotIn("order simulated successfully", visible)

    def test_replayed_approval_is_refused(self):
        req, _, _ = self.create_demo()
        self.press(f"hitl:approve:{req.request_id}")
        q = self.press(f"hitl:approve:{req.request_id}")
        q.edit_message_text.assert_not_called()
        self.assertIn("already approved", q.answer.call_args.kwargs["text"])

    def test_reject_then_approve_is_refused(self):
        req, _, _ = self.create_demo()
        self.press(f"hitl:reject:{req.request_id}")
        q = self.press(f"hitl:approve:{req.request_id}")
        q.edit_message_text.assert_not_called()
        self.assertEqual(req.status, approval_gate.ApprovalStatus.REJECTED)

    def test_request_for_another_user_is_refused(self):
        # e.g. TELEGRAM_ALLOWED_USER_ID changed after the card was sent
        req = bot.approval_gate.GATE.create(STRANGER, bot.DEMO_ACTION)
        q = self.press(f"hitl:approve:{req.request_id}")
        q.edit_message_text.assert_not_called()
        self.assertIn("different user", q.answer.call_args.kwargs["text"])
        self.assertEqual(req.status, approval_gate.ApprovalStatus.PENDING)

    def test_malformed_and_unknown_ids_are_refused(self):
        for data in ("hitl:approve:", "hitl:launch:abc", "hitl:approve:unknown-id"):
            q = self.press(data)
            q.edit_message_text.assert_not_called()

    def test_expired_request_is_cancelled_and_card_updated(self):
        gate = approval_gate.ApprovalGate(ttl_seconds=0.05)
        with patch.object(bot.approval_gate, "GATE", gate):
            req = gate.create(OWNER, bot.DEMO_ACTION)
            card = MagicMock()
            card.edit_text = AsyncMock()
            run(bot._expire_after_deadline(req.request_id, card))
            self.assertEqual(req.status, approval_gate.ApprovalStatus.EXPIRED)
            self.assertIn("expired", card.edit_text.call_args.args[0])
            q = self.press(f"hitl:approve:{req.request_id}")
            self.assertIn("expired", q.answer.call_args.kwargs["text"])
            self.assertIn("expired", q.edit_message_text.call_args.args[0])


# --------------------------------------------------------------------------- #
# Browser approvals wired through the bot
# --------------------------------------------------------------------------- #

class BrowserApprovalWiringTests(BotTestCase):
    def test_bot_passes_an_approval_function_that_uses_the_gate(self):
        details = {"kind": "click", "site": "shop.example", "url": "https://shop.example/", "target_label": "Buy", "target_tag": "button"}
        outcome = {}

        def fake_browse(task, on_step, approval_fn):
            gate = bot.approval_gate.GATE
            # Approve from "Telegram" shortly after the card is sent.
            def approve_soon():
                import time
                for _ in range(100):
                    if gate._requests:
                        rid = next(iter(gate._requests))
                        gate.decide(rid, OWNER, True)
                        return
                    time.sleep(0.01)
            import threading
            threading.Thread(target=approve_soon).start()
            status, rid = approval_fn(details)
            outcome["status"], outcome["rid"] = status, rid
            return True, "done", "https://shop.example/"

        with patch.object(bot.browser_service, "browse_and_answer", side_effect=fake_browse):
            update = make_update(OWNER)
            run(bot.call_browser_handler(update, MagicMock(args=[]), custom_task="buy it"))

        self.assertEqual(outcome["status"], approval_gate.ApprovalStatus.APPROVED)
        req = bot.approval_gate.GATE.get(outcome["rid"])
        self.assertEqual(req.user_id, OWNER)
        self.assertEqual(req.action, details)
        sent = update.message.reply_text.return_value
        card_text = sent.reply_text.call_args.args[0]
        self.assertIn("Approval needed", assert_telegram_html(self, card_text))

    def test_second_browser_task_is_refused_while_one_runs(self):
        async def scenario():
            await bot._browser_task_lock.acquire()
            try:
                update = make_update(OWNER)
                await bot.call_browser_handler(update, MagicMock(args=[]))
                return sent_texts(update)[0]
            finally:
                bot._browser_task_lock.release()
        with patch.object(bot, "_browser_task_lock", asyncio.Lock()):
            self.assertIn("already running", run(scenario()))


# --------------------------------------------------------------------------- #
# Logging & local files
# --------------------------------------------------------------------------- #

class LoggingTests(BotTestCase):
    def test_user_instruction_is_redacted_in_logs(self):
        with patch.object(bot, "call_browser_handler", AsyncMock()), \
             self.assertLogs("LocalPilot", level="INFO") as logs:
            run(bot.message_handler(make_update(OWNER, text="open example.com, my password is hunter2"), MagicMock()))
        joined = "\n".join(logs.output)
        self.assertNotIn("hunter2", joined)
        self.assertIn("REDACTED", joined)

    def test_setup_logging_redacts_file_output_and_quiets_httpx(self):
        import logging
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        saved_flag = getattr(root, "_localpilot_configured", False)
        root._localpilot_configured = False
        try:
            with patch.object(bot, "LOG_FILE", os.path.join(tmp, "test.log")):
                bot.setup_logging()
                logging.getLogger("telegram.test").warning(
                    "POST https://api.telegram.org/bot1234567890:AAFakeFakeFakeFakeFakeFakeFakeFake123/getMe")
                for handler in root.handlers:
                    handler.flush()
                with open(os.path.join(tmp, "test.log"), encoding="utf-8") as f:
                    content = f.read()
            self.assertIn("REDACTED_TELEGRAM_TOKEN", content)
            self.assertNotIn("AAFakeFake", content)
            self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        finally:
            for handler in root.handlers[:]:
                if handler not in saved_handlers:
                    root.removeHandler(handler)
                    handler.close()
            root.setLevel(saved_level)
            root._localpilot_configured = saved_flag


class GitIgnoreTests(unittest.TestCase):
    PATHS = (".env", ".env.local", "token.json", "credentials.json", "vault/vault.db", "vault/.vault_key",
             "localpilot.log", "browser_data/Default/Cookies", "user_data/x", "trace.zip", "session.har")

    def test_sensitive_files_are_ignored(self):
        repo = os.path.dirname(os.path.abspath(__file__))
        if shutil.which("git") is None or not os.path.isdir(os.path.join(repo, ".git")):
            self.skipTest("git repository not available")
        for path in self.PATHS:
            result = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=repo, check=False)
            self.assertEqual(result.returncode, 0, f"{path} is not ignored by .gitignore")
        result = subprocess.run(["git", "check-ignore", "-q", "--no-index", ".env.example"], cwd=repo, check=False)
        self.assertNotEqual(result.returncode, 0, ".env.example must stay tracked")


if __name__ == "__main__":
    unittest.main()
