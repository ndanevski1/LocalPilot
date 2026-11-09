"""
LocalPilot — Browser action policy (SRS Module 3 classification)

Every action the model proposes is validated and classified *in code*. The model
cannot change the classification, skip the policy checks, or approve anything:

  * READ_ONLY       – navigation over http(s), following a normal link, typing a
                      query into a search box, finishing with an answer.
  * STATE_CHANGING  – any other click (buttons, JS handlers, form controls) or
                      typing into a non-search field. Requires policy checks and
                      a human approval in Telegram before it runs.
  * BLOCKED         – never allowed (non-http schemes, password fields, unknown
                      elements, malformed actions).

Policy checks that run before an approval is requested:
  * the website is on the allow-list (LOCALPILOT_ALLOWED_SITES)
  * the action details are complete
  * purchases state an amount within the spending limit (LOCALPILOT_SPEND_LIMIT)
"""

import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

READ_ONLY = "read_only"
STATE_CHANGING = "state_changing"
BLOCKED = "blocked"

ALLOWED_ACTIONS = {"navigate", "click", "type", "finish"}
SAFE_SCHEMES = {"http", "https"}
MAX_TYPED_TEXT = 500
DEFAULT_SPEND_LIMIT = 0.0

PURCHASE_KEYWORDS = (
    "buy", "checkout", "check out", "place order", "place your order", "pay ", "pay now",
    "purchase", "add to cart", "add to basket", "subscribe", "donate", "order now",
    "confirm order", "book now", "complete order", "submit order",
)
SEARCH_FIELD_NAMES = {"q", "query", "search", "s", "k", "search_query", "term", "keyword", "keywords"}


@dataclass(frozen=True)
class Policy:
    allowed_sites: Tuple[str, ...] = field(default_factory=tuple)
    spend_limit: float = DEFAULT_SPEND_LIMIT
    currency: str = "USD"


def load_policy_from_env() -> Policy:
    """Reads LOCALPILOT_ALLOWED_SITES (comma-separated) and LOCALPILOT_SPEND_LIMIT."""
    raw_sites = os.getenv("LOCALPILOT_ALLOWED_SITES", "")
    sites = tuple(
        s.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
        for s in raw_sites.split(",")
        if s.strip()
    )
    try:
        limit = float(os.getenv("LOCALPILOT_SPEND_LIMIT", str(DEFAULT_SPEND_LIMIT)))
    except ValueError:
        limit = DEFAULT_SPEND_LIMIT
    currency = os.getenv("LOCALPILOT_CURRENCY", "USD").strip() or "USD"
    return Policy(allowed_sites=sites, spend_limit=max(0.0, limit), currency=currency)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def domain_of(url: str) -> str:
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host.removeprefix("www.")


def site_allowed(url: str, allowed_sites: Tuple[str, ...]) -> bool:
    host = domain_of(url)
    if not host:
        return False
    return any(host == site or host.endswith("." + site) for site in allowed_sites)


def is_safe_url(url: Any) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except ValueError:
        return False
    return parsed.scheme.lower() in SAFE_SCHEMES and bool(parsed.netloc)


def _is_plain_link(element: Dict[str, Any]) -> bool:
    if element.get("tag") != "a":
        return False
    href = (element.get("href") or "").strip()
    if not href or href.startswith("#"):
        return False
    scheme = urllib.parse.urlparse(href).scheme.lower()
    return scheme in ("", "http", "https")


def _is_search_field(element: Dict[str, Any]) -> bool:
    if element.get("tag") not in ("input", "textarea"):
        return False
    if (element.get("type") or "").lower() == "search":
        return True
    if (element.get("role") or "").lower() == "searchbox":
        return True
    if element.get("in_search_form"):
        return True
    return (element.get("name") or "").lower() in SEARCH_FIELD_NAMES


def is_purchase(action: Dict[str, Any], element: Optional[Dict[str, Any]]) -> bool:
    haystack = " ".join(
        str(x) for x in (
            (element or {}).get("label", ""),
            action.get("text", ""),
        )
    ).lower() + " "
    return any(k in haystack for k in PURCHASE_KEYWORDS)


def find_element(elements: List[Dict[str, Any]], element_id: Any) -> Optional[Dict[str, Any]]:
    return next((e for e in elements if e.get("id") == element_id), None)


# --------------------------------------------------------------------------- #
# Validation & classification
# --------------------------------------------------------------------------- #

def classify_action(action: Any, elements: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Returns (category, reason) for a model-proposed action."""
    if not isinstance(action, dict):
        return BLOCKED, "Action is not a JSON object."
    kind = action.get("action")
    if kind not in ALLOWED_ACTIONS:
        return BLOCKED, f"Unsupported action: {kind!r}."

    if kind == "finish":
        return READ_ONLY, "Finishing with an answer."

    if kind == "navigate":
        if not is_safe_url(action.get("url")):
            return BLOCKED, "Navigation is only allowed to http(s) URLs."
        return READ_ONLY, "Plain page navigation (HTTP GET)."

    element = find_element(elements, action.get("element_id"))
    if element is None:
        return BLOCKED, "The element ID does not exist on the current page."

    if kind == "click":
        if _is_plain_link(element):
            return READ_ONLY, "Following a normal link."
        return STATE_CHANGING, f"Clicking a <{element.get('tag')}> can submit or change data."

    # kind == "type"
    text = action.get("text", "")
    if not isinstance(text, str):
        return BLOCKED, "Typed text must be a string."
    if len(text) > MAX_TYPED_TEXT:
        return BLOCKED, "Typed text is too long."
    if (element.get("type") or "").lower() == "password":
        return BLOCKED, "The model may never type into password fields."
    if element.get("tag") not in ("input", "textarea") and not element.get("editable"):
        return BLOCKED, "Typing is only allowed into editable fields."
    if _is_search_field(element):
        return READ_ONLY, "Typing a query into a search box."
    return STATE_CHANGING, "Typing into a form field can submit or change data."


def build_action_details(action: Dict[str, Any], element: Optional[Dict[str, Any]], current_url: str) -> Dict[str, Any]:
    """The exact, human-readable details that are shown for approval and fingerprinted."""
    element = element or {}
    details = {
        "kind": action.get("action"),
        "site": domain_of(current_url),
        "url": current_url,
        "element_id": action.get("element_id"),
        "target_tag": element.get("tag", ""),
        "target_label": element.get("label", ""),
        "target_href": element.get("href", ""),
    }
    if action.get("action") == "type":
        details["text"] = action.get("text", "")
        details["press_enter"] = bool(action.get("press_enter", True))
    if is_purchase(action, element):
        details["purchase"] = True
        details["amount"] = action.get("amount")
        details["currency"] = action.get("currency")
    return details


def check_state_changing(details: Dict[str, Any], policy: Policy) -> List[str]:
    """Runs the pre-approval policy checks. Returns a list of problems (empty = OK)."""
    problems: List[str] = []

    if not policy.allowed_sites:
        problems.append("No websites are allowed for state-changing actions (set LOCALPILOT_ALLOWED_SITES).")
    elif not site_allowed(details.get("url", ""), policy.allowed_sites):
        problems.append(f"Website '{details.get('site') or 'unknown'}' is not on the allowed list.")

    if not details.get("site") or not details.get("url"):
        problems.append("Action details are incomplete: the website is unknown.")
    if not str(details.get("target_label") or "").strip():
        problems.append("Action details are incomplete: the target element has no visible label.")
    if details.get("kind") == "type" and not str(details.get("text") or "").strip():
        problems.append("Action details are incomplete: no text to type.")

    if details.get("purchase"):
        amount = details.get("amount")
        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            amount_value = None
        if amount_value is None or amount_value <= 0 or not re.fullmatch(r"\d+(\.\d{1,2})?", str(amount).strip()):
            problems.append("Purchase details are incomplete: the amount is missing or invalid.")
        elif amount_value > policy.spend_limit:
            problems.append(
                f"Amount {amount_value:.2f} exceeds the spending limit of {policy.spend_limit:.2f} {policy.currency}."
            )
        currency = (details.get("currency") or policy.currency or "").upper()
        if currency != policy.currency.upper():
            problems.append(f"Purchase currency must be {policy.currency}.")

    return problems
