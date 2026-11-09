"""Tests for action_policy.py: read-only vs state-changing classification and pre-approval checks."""

import os
import unittest
from unittest.mock import patch

import action_policy as ap

LINK = {"id": "e0", "tag": "a", "type": "", "label": "Docs", "href": "/docs"}
JS_LINK = {"id": "e1", "tag": "a", "type": "", "label": "Open menu", "href": "javascript:void(0)"}
BUTTON = {"id": "e2", "tag": "button", "type": "submit", "label": "Place order", "href": ""}
SEARCH = {"id": "e3", "tag": "input", "type": "search", "label": "Search", "href": "", "name": "q"}
TEXT_FIELD = {"id": "e4", "tag": "input", "type": "text", "label": "Comment", "href": "", "name": "comment"}
PASSWORD = {"id": "e5", "tag": "input", "type": "password", "label": "Password", "href": ""}
UNLABELED_BUTTON = {"id": "e6", "tag": "button", "type": "", "label": "", "href": ""}
ELEMENTS = [LINK, JS_LINK, BUTTON, SEARCH, TEXT_FIELD, PASSWORD, UNLABELED_BUTTON]

POLICY = ap.Policy(allowed_sites=("shop.example",), spend_limit=50.0, currency="USD")
SHOP_URL = "https://www.shop.example/cart"


class ClassificationTests(unittest.TestCase):
    def classify(self, action):
        return ap.classify_action(action, ELEMENTS)[0]

    # ---- read-only ----
    def test_finish_is_read_only(self):
        self.assertEqual(self.classify({"action": "finish", "answer": "x"}), ap.READ_ONLY)

    def test_https_navigation_is_read_only(self):
        self.assertEqual(self.classify({"action": "navigate", "url": "https://example.com"}), ap.READ_ONLY)

    def test_plain_link_click_is_read_only(self):
        self.assertEqual(self.classify({"action": "click", "element_id": "e0"}), ap.READ_ONLY)

    def test_typing_into_search_box_is_read_only(self):
        self.assertEqual(self.classify({"action": "type", "element_id": "e3", "text": "usb cable"}), ap.READ_ONLY)

    # ---- state-changing ----
    def test_button_click_is_state_changing(self):
        self.assertEqual(self.classify({"action": "click", "element_id": "e2"}), ap.STATE_CHANGING)

    def test_javascript_link_is_state_changing(self):
        self.assertEqual(self.classify({"action": "click", "element_id": "e1"}), ap.STATE_CHANGING)

    def test_typing_into_form_field_is_state_changing(self):
        self.assertEqual(self.classify({"action": "type", "element_id": "e4", "text": "hi"}), ap.STATE_CHANGING)

    # ---- blocked ----
    def test_non_http_navigation_is_blocked(self):
        for url in ("javascript:alert(1)", "file:///C:/Windows/win.ini", "chrome://settings", "data:text/html,x", ""):
            self.assertEqual(self.classify({"action": "navigate", "url": url}), ap.BLOCKED, url)

    def test_password_field_is_blocked(self):
        self.assertEqual(self.classify({"action": "type", "element_id": "e5", "text": "x"}), ap.BLOCKED)

    def test_unknown_element_is_blocked(self):
        self.assertEqual(self.classify({"action": "click", "element_id": "e99"}), ap.BLOCKED)

    def test_unknown_action_is_blocked(self):
        self.assertEqual(self.classify({"action": "approve"}), ap.BLOCKED)
        self.assertEqual(self.classify({"action": "execute_js", "code": "x"}), ap.BLOCKED)
        self.assertEqual(ap.classify_action("not a dict", ELEMENTS)[0], ap.BLOCKED)

    def test_typing_into_button_is_blocked(self):
        self.assertEqual(self.classify({"action": "type", "element_id": "e2", "text": "x"}), ap.BLOCKED)

    def test_overlong_text_is_blocked(self):
        self.assertEqual(self.classify({"action": "type", "element_id": "e3", "text": "a" * 501}), ap.BLOCKED)


class PolicyCheckTests(unittest.TestCase):
    def details(self, action, element, url=SHOP_URL):
        return ap.build_action_details(action, element, url)

    def test_allowed_site_with_complete_details_passes(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "19.99"}, BUTTON)
        self.assertEqual(ap.check_state_changing(d, POLICY), [])

    def test_site_not_on_allow_list_is_blocked(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "1"}, BUTTON, "https://evil.example/x")
        problems = ap.check_state_changing(d, POLICY)
        self.assertTrue(any("not on the allowed list" in p for p in problems))

    def test_lookalike_domain_is_blocked(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "1"}, BUTTON, "https://shop.example.evil.test/")
        self.assertTrue(ap.check_state_changing(d, POLICY))

    def test_empty_allow_list_blocks_everything(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "1"}, BUTTON)
        problems = ap.check_state_changing(d, ap.Policy())
        self.assertTrue(any("No websites are allowed" in p for p in problems))

    def test_purchase_over_spending_limit_is_blocked(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "50.01"}, BUTTON)
        problems = ap.check_state_changing(d, POLICY)
        self.assertTrue(any("exceeds the spending limit" in p for p in problems))

    def test_purchase_at_spending_limit_passes(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "50.00"}, BUTTON)
        self.assertEqual(ap.check_state_changing(d, POLICY), [])

    def test_purchase_without_amount_is_incomplete(self):
        d = self.details({"action": "click", "element_id": "e2"}, BUTTON)
        problems = ap.check_state_changing(d, POLICY)
        self.assertTrue(any("amount is missing" in p for p in problems))

    def test_purchase_with_bad_amount_is_incomplete(self):
        for amount in ("-5", "abc", "0", "1e9", "12.345"):
            d = self.details({"action": "click", "element_id": "e2", "amount": amount}, BUTTON)
            self.assertTrue(ap.check_state_changing(d, POLICY), amount)

    def test_wrong_currency_is_blocked(self):
        d = self.details({"action": "click", "element_id": "e2", "amount": "5", "currency": "EUR"}, BUTTON)
        self.assertTrue(any("currency" in p for p in ap.check_state_changing(d, POLICY)))

    def test_unlabeled_target_is_incomplete(self):
        d = self.details({"action": "click", "element_id": "e6"}, UNLABELED_BUTTON)
        self.assertTrue(any("no visible label" in p for p in ap.check_state_changing(d, POLICY)))

    def test_typing_without_text_is_incomplete(self):
        d = self.details({"action": "type", "element_id": "e4", "text": "  "}, TEXT_FIELD)
        self.assertTrue(any("no text" in p for p in ap.check_state_changing(d, POLICY)))

    def test_policy_loaded_from_environment(self):
        env = {"LOCALPILOT_ALLOWED_SITES": "https://www.Shop.example/, other.test", "LOCALPILOT_SPEND_LIMIT": "25"}
        with patch.dict(os.environ, env):
            policy = ap.load_policy_from_env()
        self.assertEqual(policy.allowed_sites, ("shop.example", "other.test"))
        self.assertEqual(policy.spend_limit, 25.0)

    def test_policy_defaults_are_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            policy = ap.load_policy_from_env()
        self.assertEqual(policy.allowed_sites, ())
        self.assertEqual(policy.spend_limit, 0.0)


if __name__ == "__main__":
    unittest.main()
