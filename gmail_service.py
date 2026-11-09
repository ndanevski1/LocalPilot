"""
LocalPilot — Gmail Integration Service
Module 4: Email Execution Engine via Google OAuth 2.0 (Read-Only)
"""

import os
import html
import logging
from typing import Optional, List, Dict, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from safety import h, truncate

logger = logging.getLogger("LocalPilot.Gmail")

# Where users can fully revoke LocalPilot's Google authorization grant.
GOOGLE_PERMISSIONS_URL = "https://myaccount.google.com/permissions"

# Allow Google OAuth server to return additional default scopes (like openid) without throwing ScopeChanged error
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Read-only scopes for safety and least privilege
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def get_credentials() -> Optional[Credentials]:
    """Retrieves valid user credentials from token.json or refreshes if expired."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.error(f"Error loading {TOKEN_FILE}: {e}")
            return None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info("Refreshing expired Google OAuth access token...")
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as token:
                token.write(creds.to_json())
            return creds
        except Exception as e:
            logger.error(f"Failed to refresh Google OAuth token: {e}")
            return None

    return None


def is_connected() -> bool:
    """Checks whether a valid Google OAuth session exists."""
    creds = get_credentials()
    return creds is not None and creds.valid


def get_connected_email() -> Optional[str]:
    """Retrieves the email address of the authenticated Gmail account."""
    creds = get_credentials()
    if not creds:
        return None

    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception as e:
        logger.error(f"Could not fetch Gmail profile: {e}")
        return None


def authenticate() -> Tuple[bool, str]:
    """
    Launches the Google OAuth 2.0 loopback server in the local browser.
    Stores the offline refresh token into token.json.
    """
    if is_connected():
        email = get_connected_email() or "authenticated user"
        return True, f"Already connected as `{email}`."

    if not os.path.exists(CREDENTIALS_FILE):
        return (
            False,
            "Missing `credentials.json` in project root! Please download your OAuth Client ID from Google Cloud Console.",
        )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        logger.info("Opening local browser for Google OAuth 2.0 consent...")
        # run_local_server opens the browser on the host machine and listens on a free loopback port
        creds = flow.run_local_server(port=0, prompt="consent")

        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

        # Retrieve verified email
        email = get_connected_email() or "Google User"
        return True, f"Successfully connected Gmail account: `{email}`"
    except Exception as e:
        logger.error(f"OAuth authentication error: {e}")
        return False, f"Authentication failed: {str(e)}"


REVOKE_NOTE = (
    "Deleting token.json only removes the token stored on this computer. It does not "
    "necessarily revoke the authorization you granted to LocalPilot in your Google account. "
    f"To revoke it completely, remove LocalPilot at {GOOGLE_PERMISSIONS_URL}"
)


def disconnect() -> Tuple[bool, str]:
    """
    Removes the local token.json file (local opt-out).
    This does NOT revoke the Google authorization grant; see REVOKE_NOTE.
    """
    if os.path.exists(TOKEN_FILE):
        try:
            os.remove(TOKEN_FILE)
            logger.info("Local token.json deleted.")
            return True, "Gmail has been disconnected on this computer. The local token file was deleted."
        except Exception as e:
            logger.error(f"Failed to delete token file: {type(e).__name__}")
            return False, "Failed to remove the local token file. Check file permissions and try again."
    return True, "Gmail was not connected on this computer."


def get_unread_emails(max_results: int = 5) -> Tuple[bool, List[Dict], str]:
    """
    Fetches the latest unread emails from the user's primary inbox.
    Returns: (success: bool, email_list: list, message: str)
    """
    creds = get_credentials()
    if not creds:
        return False, [], "Gmail is not connected. Use /connect_gmail to authenticate."

    try:
        service = build("gmail", "v1", credentials=creds)

        # Query unread messages strictly in primary category (filters out Promotions, Social, Updates, Forums)
        query = "is:unread category:primary"
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            return True, [], "🎉 You have no unread emails in your Primary inbox!"

        emails = []
        for msg in messages:
            msg_id = msg["id"]
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            sender = headers.get("From", "Unknown Sender")
            subject = headers.get("Subject", "(No Subject)")
            date = headers.get("Date", "")
            snippet = msg_data.get("snippet", "")

            # Clean and sanitize snippet text
            clean_snippet = html.unescape(snippet).strip()

            emails.append(
                {
                    "id": msg_id,
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "snippet": clean_snippet,
                }
            )

        return True, emails, f"Found {len(emails)} unread emails."

    except HttpError as error:
        logger.error(f"Gmail API HTTP error: {error}")
        return False, [], f"Google API Error: {error.reason}"
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        return False, [], f"Unexpected error: {str(e)}"


def format_email_digest(emails: List[Dict]) -> str:
    """
    Formats a list of email dictionaries into a Telegram HTML summary.
    Sender, subject and preview are escaped, so any characters are safe.
    The digest is sent to Telegram only and is never written to logs.
    """
    if not emails:
        return "📭 <b>Inbox Zero:</b> No unread messages in your Primary inbox."

    output = [f"📬 <b>Primary Inbox Digest ({len(emails)} unread)</b>\n"]
    for i, mail in enumerate(emails, 1):
        sender = truncate(mail.get("sender", ""), 120)
        subject = truncate(mail.get("subject", ""), 200)
        snippet = truncate(mail.get("snippet", ""), 120)

        output.append(f"<b>{i}. {h(subject)}</b>")
        output.append(f"• <b>From:</b> <code>{h(sender)}</code>")
        if snippet:
            output.append(f"• <b>Preview:</b> <i>{h(snippet)}</i>")
        output.append("")  # Blank line separator

    output.append("💡 <i>LocalPilot Module 4: Gmail REST API Engine</i>")
    return "\n".join(output)
