"""
LocalPilot — Curated Website Login Recipes (Module 3 Demo Suite)
Focused specifically on the 3 primary demo targets:
  1. Amazon (E-Commerce & Autonomous Purchasing Demo — two_step flow)
  2. GitHub (Developer & Repository Action Demo — single_step flow)
  3. Reddit (Social, Forum & Community Action Demo — single_step flow)
"""

from typing import Dict, Any, Optional

LOGIN_RECIPES: Dict[str, Dict[str, Any]] = {
    # ─── 1. Amazon (Two-Step Split Flow) ─────────────────────────────────────
    "amazon.com": {
        "name": "Amazon",
        "category": "E-Commerce",
        "flow": "two_step",
        "login_url": "https://www.amazon.com/gp/sign-in.html",
        "username_field": "input[type='email'], input[name='email'], #ap_email",
        "continue_btn": "input#continue, span#continue, button#continue",
        "password_field": "input[type='password'], #ap_password",
        "submit_btn": "input#signInSubmit, button#signInSubmit",
        "logged_in_indicator": "#nav-link-accountList:not(:has-text('Sign in'))",
        "captcha_indicator": "#auth-captcha-image-container, iframe[title*='captcha']",
        "two_factor_indicator": "#auth-mfa-otpcode, input[name='otpCode']"
    },

    # ─── 2. GitHub (Single-Step Flow) ────────────────────────────────────────
    "github.com": {
        "name": "GitHub",
        "category": "Developer",
        "flow": "single_step",
        "login_url": "https://github.com/login",
        "username_field": "#login_field",
        "continue_btn": None,
        "password_field": "#password",
        "submit_btn": "input[name='commit']",
        "logged_in_indicator": "meta[name='user-login'], img.avatar-user",
        "captcha_indicator": "#octocaptcha, iframe[src*='arkoselabs']",
        "two_factor_indicator": "input#app_totp, input#otp"
    },

    # ─── 3. Reddit (Single-Step Flow) ────────────────────────────────────────
    "reddit.com": {
        "name": "Reddit",
        "category": "Social",
        "flow": "single_step",
        "login_url": "https://www.reddit.com/login",
        "username_field": "input[name='username']",
        "continue_btn": None,
        "password_field": "input[name='password']",
        "submit_btn": "button[type='submit']",
        "logged_in_indicator": "faceplate-tracker[noun='user_profile'], shreddit-player-2",
        "captcha_indicator": "iframe[title*='reCAPTCHA']",
        "two_factor_indicator": "input[name='otp_code']"
    }
}


def get_login_recipe(url_or_domain: str) -> Optional[Dict[str, Any]]:
    """
    Returns the matching login recipe for Amazon, GitHub, or Reddit, if applicable.
    """
    clean = url_or_domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
    for domain, recipe in LOGIN_RECIPES.items():
        if domain in clean or clean in domain:
            return recipe
    return None
