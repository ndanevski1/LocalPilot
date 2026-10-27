# LocalPilot — On-Device Personal Action Agent

[![GitHub Repository](https://img.shields.io/badge/GitHub-ndanevski1%2FLocalPilot-blue?style=flat-square&logo=github)](https://github.com/ndanevski1/LocalPilot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)

LocalPilot is an open-source, local-first autonomous AI action agent that runs directly on your computer to handle digital chores—such as compiling email digests and managing web purchases—while keeping private credentials and session data encrypted strictly on your host hardware.

> 📖 **Looking for full system specifications and architecture?**  
> See [PROJECT_DETAILS.md](PROJECT_DETAILS.md) for the complete Software Requirements Specification (SRS), team roles, and module roadmap.

---

## 💡 How LocalPilot Works: Remote Control vs. Engine

LocalPilot follows a **zero-trust, distributed architecture**. There is no central cloud server holding user passwords:

```
┌──────────────────────────────────────────────┐
│  Your Phone / Mobile Device (Android / iOS)  │ ◀── In your pocket anywhere
│          (Standard Telegram App)             │     Acts as the "Remote Control"
└──────────────────────┬───────────────────────┘
                       │ Outbound HTTPS (Telegram API)
                       ▼
┌──────────────────────────────────────────────┐
│    Your Host Computer (Windows / Mac / Linux)│ ◀── On your desk
│      (LocalPilot Python Daemon + Browser)    │     Acts as the "Autonomous Engine"
└──────────────────────────────────────────────┘
```

1. **Host Computer (The Engine):** Runs the Python daemon on your Windows, macOS, or Linux machine. This is where web automations (Playwright), local AI models (Ollama), and encrypted credential vaults reside.
2. **Mobile Device (The Remote Control):** Runs the regular Telegram messaging app (Android or iOS). You do **not** run Python or code on your phone—you simply chat with your bot to issue instructions and approve actions.
3. **Zero Port Forwarding:** Uses outbound long-polling. No open router ports, public IP addresses, or webhooks are needed.

---

## 🚀 Quickstart: Setting Up for a New User / Developer

Because LocalPilot runs locally on each user's machine, **every team member or user sets up their own local instance**.

### Prerequisites
* **Python 3.10+** installed on your host computer.
* **Git** installed on your host computer.
* A free **Telegram** account on your phone or computer.

---

### Step 1: Create Your Personal Telegram Bot

Telegram requires each independently running computer to use its own bot token:

1. Open Telegram on your phone or desktop and search for **`@BotFather`**.
2. Send `/start`, then send `/newbot`.
3. Choose a name (e.g. `Alice's LocalPilot`) and a username ending in `bot` (e.g. `alice_localpilot_bot`).
4. **Copy the HTTP API token** (e.g. `8881514588:AAFvrvIVWr...`).

---

### Step 2: Get Your Personal Telegram User ID

To make sure nobody else on Telegram can control your computer, LocalPilot locks execution to your numeric User ID:

1. In Telegram, search for **`@userinfobot`**.
2. Press **Start** (or send any message).
3. Copy the numeric **`Id`** shown (e.g. `8787403346`).

---

### Step 3: Clone the Repository & Configure Secrets

Open your terminal or command prompt on your host computer:

```bash
# Clone the repository
git clone https://github.com/ndanevski1/LocalPilot.git
cd LocalPilot
```

Create your private `.env` configuration file from the template:

* **On Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
* **On macOS / Linux (Bash or Zsh):**
  ```bash
  cp .env.example .env
  ```

Open `.env` in any text editor and fill in your credentials from Steps 1 and 2:
```env
TELEGRAM_BOT_TOKEN="your_bot_token_here"
TELEGRAM_ALLOWED_USER_ID="your_telegram_numeric_id_here"
```

> 🔒 **Security Notice:** The `.env` file is explicitly ignored in `.gitignore` and will never be pushed to GitHub.

---

### Step 4: Install Dependencies

#### On Windows (PowerShell):
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

*(Note: If PowerShell blocks script execution, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first).*

#### On macOS / Linux (Terminal):
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

---

### Step 5: Start the LocalPilot Daemon

Start the agent on your host machine:

* **Windows:**
  ```powershell
  python bot.py
  ```
* **macOS / Linux:**
  ```bash
  python3 bot.py
  ```

You will see output confirming:
```text
[LocalPilot] - INFO - Initializing LocalPilot Telegram Bot with Gmail Engine...
[LocalPilot] - INFO - LocalPilot Telegram Bot is running (Long-polling active)...
[LocalPilot] - INFO - Press Ctrl+C to terminate the daemon.
```

---

### Step 6 (Optional): Connect Your Gmail Account

LocalPilot can read and summarize your **Primary inbox** (Promotions, Social, and Updates are automatically filtered out) via read-only Google OAuth 2.0. This step is entirely optional — the bot runs fully without it.

#### Authenticate (One-Time Setup)

Run the interactive setup script directly in your terminal (not as a background process — it must open your browser):

* **Windows:**
  ```powershell
  .\venv\Scripts\python setup_gmail.py
  ```
* **macOS / Linux:**
  ```bash
  python3 setup_gmail.py
  ```

Your browser will open with Google's consent screen. Select your account and grant **Read-Only** access. Once you see *"The authentication flow has completed"* in your browser, your `token.json` is saved and the bot is ready.

To opt out at any time, send `/disconnect_gmail` from Telegram or delete `token.json` from your project folder.

---

## 📱 How to Use & Test from Your Mobile Device (Android / iOS / Mac)

Now that the daemon is running on your host computer:

1. Open the **Telegram app** on your **Android phone**, **iPhone**, or **Mac**.
2. Open the chat with your bot (the username you registered with `@BotFather`).
3. Send **`/start`**.

### Available Commands & Interactive Demos:

| Command | Action |
| :--- | :--- |
| **`/start`** | Displays session information, security status, Gmail connection state, and interactive navigation menu. |
| **`📊 System Status`** (`/status`) | Queries the host computer in real-time and returns OS platform, Python version, Gmail connection, and connectivity diagnostics. |
| **`📬 Unread Email Digest`** (`/summary`) | Fetches the 5 latest unread emails from your **Primary inbox** (Promotions, Social, and Updates filtered out). |
| **`🔗 Connect Gmail`** (`/connect_gmail`) | Displays instructions for running the one-time `setup_gmail.py` Google OAuth flow on the host computer. |
| **`🔌 Disconnect Gmail`** (`/disconnect_gmail`) | Deletes the local `token.json` session token to immediately opt out of Gmail access. |
| **`🛡️ Test HITL Approval`** (`/demo_hitl`) | Triggers a **Human-in-the-Loop** simulation card with **[Approve ✅]** and **[Reject ❌]** buttons (demonstrating SRS Module 3). |
| **`❓ Help`** (`/help`) | Displays operator command reference. |
| **Natural Language Prompts** | Send any text message (e.g., *"Summarize my unread emails"* or *"Give me my email digest"*) to test natural language dispatch. |

---

## ❓ Frequently Asked Questions (FAQ)

#### 1. Can multiple developers use the exact same Bot Token simultaneously?
**No.** Telegram's long-polling protocol only permits **one active connection per bot token at a time**. If two computers run `python bot.py` with the same token, Telegram will terminate one with a `Conflict` error. Every developer should create their own bot handle via `@BotFather`.

#### 2. Why doesn't the Python script run directly on an Android device?
Desktop web automation (Playwright/Chromium), encrypted SQLite vaults, and local LLMs (Ollama) require desktop operating system capabilities and compute power. Android aggressively terminates background processes to save battery. The phone is intentionally designed to serve as a lightweight **remote control**, while your computer acts as the **worker**.

#### 3. What happens if an unauthorized person messages my bot?
If `TELEGRAM_ALLOWED_USER_ID` is set in your `.env`, LocalPilot will reject any incoming commands or callbacks from unfamiliar users with an `⛔ Access Denied` alert.

#### 4. Does my computer need to stay on?
Yes. Because LocalPilot is a local-first agent that runs private tasks on your hardware, the host machine must be on and running `bot.py` while receiving remote instructions.

#### 5. Can multiple team members share the same Google OAuth Client ID (`credentials.json`)?
**Yes.** The `credentials.json` file identifies the *application* (LocalPilot) to Google and is safe to share across your team via a private channel. Each team member goes through the OAuth flow independently using their own Google account, and each person's private session token (`token.json`) is stored only on their own local machine. No one can read another person's emails.


