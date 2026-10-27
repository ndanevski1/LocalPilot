"""
LocalPilot — One-Time Gmail OAuth Setup
Run this in your terminal to authenticate your Google Account.
"""

import os
import sys

# Relax token scope check so Google's default 'openid' scope does not trigger ScopeChanged exception
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import gmail_service


def main():
    print("=" * 60)
    print(" LocalPilot — Gmail OAuth 2.0 Desktop Authentication")
    print("=" * 60)

    if gmail_service.is_connected():
        email = gmail_service.get_connected_email() or "Authorized Account"
        print(f"\n✅ Gmail is ALREADY connected as: {email}")
        print("Your token.json is active. You can now use /summary in Telegram!\n")
        return

    print("\nOpening your default browser for Google Sign-In...")
    print("Please select your Google account and grant Read-Only access.\n")

    success, message = gmail_service.authenticate()
    print("-" * 60)
    print(message)
    print("-" * 60)

    if success:
        print("\n🎉 Setup complete! You can now use /summary in Telegram from your phone.")
    else:
        print("\n❌ Setup failed. Please review the error message above.")


if __name__ == "__main__":
    main()
