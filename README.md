# LocalPilot — On-Device Personal Action Agent

[![GitHub Repository](https://img.shields.io/badge/GitHub-ndanevski1%2FLocalPilot-blue?style=flat-square&logo=github)](https://github.com/ndanevski1/LocalPilot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)

LocalPilot is an open-source, local-first AI action agent that runs directly on your computer. Today it summarizes your Gmail inbox and runs supervised web-browsing tasks with a local model; web purchases with stored credentials are planned. Everything runs on your host machine, controlled from Telegram.

> 📖 **Looking for full system specifications and architecture?**  
> See [PROJECT_DETAILS.md](PROJECT_DETAILS.md) for the complete Software Requirements Specification (SRS), team roles, and module roadmap.
> 
> 💡 **Looking for ready-to-use sample queries?**  
> See [example_user_prompts.md](example_user_prompts.md) for 10 verified instructions covering email digests, knowledge extraction, GitHub searches, and approval workflows.

---

## ✅ Feature Status

What the code does today, what is only a demonstration, and what is still planned.

### Implemented
* **Telegram remote control** (`bot.py`): outbound long-polling, no open ports. Every command, message and button press is checked against `TELEGRAM_ALLOWED_USER_ID`.
* **Locked-down setup mode:** if `TELEGRAM_ALLOWED_USER_ID` is empty, the bot only tells you your own Telegram ID; every feature is disabled. With `LOCALPILOT_ENV=production` the bot refuses to start without it.
* **Gmail digest** (`gmail_service.py`): read-only OAuth scope (`gmail.readonly`), 5 latest unread Primary-inbox emails. Email content is sent to Telegram only and never logged.
* **Autonomous browser agent** (`browser_service.py`): Playwright (visible Chromium) + local Ollama `qwen2.5:3b`, with live Pause / Go Back / Stop controls.
* **Human-in-the-Loop approval gate for the browser agent** (`action_policy.py`, `approval_gate.py`): every action is classified as read-only or state-changing *in code*. State-changing actions (button clicks, form typing) must pass website, spending and completeness checks, then wait for your **Approve** in Telegram. Approvals are tied to your user ID, single-use, bound to the exact action, and expire after 30 minutes.
* **Prompt-injection and secret safeguards:** webpage text is fenced as untrusted data; passwords, tokens and card numbers are redacted from every model prompt and from `localpilot.log`; form-field values are never read from pages; the agent never types into password fields.
* **Zero-shot pre-flight intent decomposition** (`browser_service.py`): Qwen parses compound instructions into `target_site`, clean `search_keyword` (proper nouns/entities), and `extraction_goal` before Chromium launches, preventing conversational phrasing from polluting search queries.
* **Content-first DOM element prioritization & 4,500-char semantic window** (`browser_service.py`): interactive elements in core content (`<main>`, `<article>`, search cards) take precedence over navigation chrome (`<header>`, `<nav>`, sidebars), surfacing up to 45 actionable elements and a 4,500-character snapshot to Qwen.
* **Search engine navigation guardrails** (`browser_service.py`): when the agent lands on search pages (e.g. `/search`, `?search=`, `?q=`), Qwen is constrained to click the most relevant article link rather than prematurely finishing on search notice boilerplate.
* **Persistent browser session caching & curated login recipes** (`browser_service.py`, `login_recipes.py`): Chromium cookies and session storage persist across runs in `vault/browser_profile/` (git-ignored, never committed). Includes curated deterministic selectors, 2FA, and CAPTCHA detection indicators for Amazon (two-step OpenID), GitHub, and Reddit.
* **Automated 404 recovery bridge** (`browser_service.py`): broken URLs and HTTP 404 pages are intercepted automatically, falling back to a Google Search bridge to locate working target links without stalling the loop.
* **Local credential vault dashboard** (`vault_app.py`, `vault_service.py`): `http://127.0.0.1:8080`, SQLite with Fernet-encrypted password field (see [Step 7](#step-7-optional-manage-stored-credentials-via-local-vault-dashboard) for its real limits).

### Demonstration only
* **`/demo_hitl`** shows a *simulated* purchase approval. It uses the real approval gate (tracking, single use, 30-minute expiry) but nothing is bought, no payment is made and no credentials are used.

### Planned (not implemented)
* Using vault credentials in the browser (local credential injection with placeholder tokens).
* Real purchases / checkout flows (state-changing actions are gated, but there is no purchase workflow).
* Windows PIN / Windows Hello protection for revealing vault passwords.
* SQLCipher whole-database encryption and AES-256 (the current Fernet scheme uses AES-128-CBC + HMAC).
* Hybrid local/cloud model routing (only the local Ollama model is used), FastAPI / WebSockets backend, ARIA accessibility-tree parsing, screenshots in Telegram.

---

## 💡 How LocalPilot Works: Remote Control vs. Engine

LocalPilot follows a **local-first, distributed architecture**. There is no central cloud server holding user passwords:

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

1. **Host Computer (The Engine):** Runs the Python daemon on your Windows, macOS, or Linux machine. This is where web automations (Playwright), the local AI model (Ollama), and the local credential vault reside.
2. **Mobile Device (The Remote Control):** Runs the regular Telegram messaging app (Android or iOS). You do **not** run Python or code on your phone—you simply chat with your bot to issue instructions and approve actions.
3. **Zero Port Forwarding:** Uses outbound long-polling. No open router ports, public IP addresses, or webhooks are needed.

---

## 🚀 Quickstart: Setting Up for a New User / Developer

Because LocalPilot runs locally on each user's machine, **every team member or user sets up their own local instance**.

### Prerequisites
* **Python 3.10+** installed on your host computer.
* **Git** installed on your host computer.
* **Ollama** installed on your host computer with the `qwen2.5:3b` model (`ollama pull qwen2.5:3b`).
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

> ⚠️ **`TELEGRAM_ALLOWED_USER_ID` is required for normal use.** If you leave it empty, the bot starts in *setup mode*: it only replies to `/start` with the sender's Telegram ID and every feature is disabled. Set `LOCALPILOT_ENV="production"` to make the bot refuse to start without it.

Optional browser-agent safety settings (defaults are the safest values):
```env
# Sites where the agent may *request approval* for state-changing actions (button clicks, form typing).
# Empty = state-changing actions are always blocked; read-only browsing still works everywhere.
LOCALPILOT_ALLOWED_SITES="example-shop.com,another-site.org"
# Maximum purchase amount the agent may request approval for. 0 = no purchases.
LOCALPILOT_SPEND_LIMIT="0"
LOCALPILOT_CURRENCY="USD"
```

> 🔒 **Security Notice:** `.env`, `token.json`, `credentials.json`, `vault/`, `localpilot.log` and browser data folders are ignored in `.gitignore` and will never be pushed to GitHub. Secrets such as the bot token are redacted from `localpilot.log`.

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

# Install Playwright browser engine
playwright install chromium
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

# Install Playwright browser engine
playwright install chromium
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

> ⚠️ **Deleting `token.json` only removes the token stored on your computer.** It does not necessarily revoke the authorization you granted to LocalPilot in your Google account. To revoke it completely, remove LocalPilot at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

The Gmail scope is read-only (`gmail.readonly`, plus `openid` and `userinfo.email` to show which account is connected). LocalPilot cannot send, delete or modify email.

---

### Step 7 (Optional): Manage Stored Credentials via Local Vault Dashboard

LocalPilot provides a clean, local-only web dashboard to manage web credentials without exposing passwords over Telegram:

```powershell
# Launch the Local Vault Dashboard in your browser
.\venv\Scripts\python vault_app.py
```

* **URL:** `http://127.0.0.1:8080` (bound to `localhost` only, not reachable from other machines).
* **Storage:** plain SQLite database (`vault/vault.db`, **not** SQLCipher). Only the password column is encrypted, using [Fernet](https://cryptography.io/en/latest/fernet/) (AES-128-CBC + HMAC-SHA256). Domains, usernames and notes are stored in plain text.
* **Key storage:** the Fernet key is stored in `vault/.vault_key` next to the database. Anyone who can read the `vault/` folder can decrypt the passwords, so protection relies on your Windows user account and its file permissions.
* **No extra authentication:** revealing or editing a password in the dashboard does **not** ask for a Windows PIN, Windows Hello or any password. Anyone using your logged-in Windows account can open the dashboard and reveal passwords. (A Windows PIN check is planned, not implemented.)
* **Auto-Masking:** revealed passwords re-mask in the browser after 15 seconds.
* **Not connected to the agent yet:** the browser agent does not read the vault; credential injection is planned.

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
| **`🔌 Disconnect Gmail`** (`/disconnect_gmail`) | Deletes the local `token.json`. This does not necessarily revoke the Google grant; the reply links to your Google account permissions page. |
| **`🛡️ Test HITL Approval`** (`/demo_hitl`) | **Simulation.** Shows a fictional purchase card with **[Approve ✅]** and **[Reject ❌]** buttons. It uses the real approval gate (single use, 30-minute expiry), but nothing is bought and no credentials are used. |
| **`🌐 Call Browser`** (`/call_browser [task]`) | Launches the visible Chromium browser on the host machine to run a browsing task via Ollama (`qwen2.5:3b`). Without a task it runs the default: *"Open https://example.com and tell me the page title."* |
| **`🔒 Close Browser`** (`/close_browser`) | Manually terminates the active browser instance and cleans up Playwright memory. |
| **`❓ Help`** (`/help`) | Displays operator command reference. |
| **Natural Language Prompts** | Send any text message (e.g., *"Open example.com and tell me the page title"* or *"Summarize my unread emails"*) to test natural language dispatch. |

---

## 🌐 Autonomous Web Browsing Engine (ReAct Architecture & DOM Parsing)

LocalPilot features an on-device, autonomous web browsing engine powered by **Playwright** (`headless=False`) and a local **Ollama** LLM (`qwen2.5:3b`). The engine allows you to prompt the agent from Telegram (e.g., *"Open example.com and tell me the page title"*), watch Chromium operate live on your host screen, and intervene at any time.

```
Telegram Instruction ──► URL Inference ──► Playwright Chromium (Visible)
                                                    │
                                         ┌──────────┴──────────┐
                                         ▼                     ▼
                             DOM Elements Extractor     <main> Snapshot
                             (Content-first, top 45)   (4,500 chars clean text)
                                         └──────────┬──────────┘
                                                    ▼
                                          Qwen 2.5:3b (Ollama)
                                          (num_predict: 128)
                                                    │
                                         ┌──────────┴──────────┐
                                         ▼                     ▼
                                {"action": "click"}    {"action": "finish"}
                                {"action": "type"}     (Returns Answer)
                                         │
                                         ▼
                             Live Telegram Card Edit
                             [⏸️ Pause] [⬅️ Go Back] [🛑 Stop]
```

### 1. How Does the Agent Choose the Initial Website & Query?
When an instruction arrives, LocalPilot uses a multi-tiered resolution pipeline to ensure it lands on an authentic URL without hallucinating broken subpaths:

1. **Zero-Shot Pre-Flight Intent Decomposition (`browser_service.py`):**
   - Before touching the browser, local Qwen decomposes compound user prompts into three normalized fields:
     - `target_site`: domain or service name (e.g. `wikipedia.org`, `github.com`, `amazon.com`, `google.com`).
     - `search_keyword`: the clean entity or proper noun (e.g. `Sofia University`, `LocalPilot`, `iPhone 16`), stripping questions and conversational filler.
     - `extraction_goal`: the precise question, fact, or task to satisfy (e.g. *"Identify who the president or rector is"*).
2. **Curated Template Match (`search_templates.py`):**
   - The engine checks a registry of **100+ popular platforms** across Academic (Google Scholar, PubMed, arXiv, Semantic Scholar), Developer (GitHub, GitLab, Stack Overflow, PyPI, Hugging Face), E-Commerce (Amazon, eBay, Best Buy), Knowledge (Wikipedia, Britannica), Social, and News sites.
   - Using `resolve_template_by_site()`, it formats the authentic search URL with exact-match precedence (e.g., `https://en.wikipedia.org/w/index.php?search=Sofia+University` or `https://github.com/search?q=LocalPilot`), saving round-trip latency.
2. **Explicit URL Detection:**
   - If the user provides a specific link or domain in their text (e.g., `https://...`, `example.com`, `sofia.edu`), the agent extracts it with regex and navigates directly there.
3. **Dynamic Root Domain Inference & Sanitization:**
   - For open-ended prompts on unlisted sites, Qwen infers the starting domain. The URL is automatically parsed and sanitized to retain only the base root homepage (e.g., `https://example.com`), preventing the LLM from inventing broken query parameters.
4. **Automated 404 & Broken Page Recovery:**
   - If any page returns an HTTP 404, "Page Not Found", or broken server response, the agent **never stalls or crashes**. It intercepts the error, alerts the user in Telegram, and automatically falls back to a Google Search bridge (`google.com/search?q={task}`) to locate the active working link.

### 2. How Do We Parse the Website Tree?
A raw HTML DOM tree on modern websites can exceed 50,000 lines of code, which would instantly exhaust the token context of on-device LLMs and cause heavy CPU latency. LocalPilot employs a **two-track extraction strategy**:

* **Track 1: Content-First Interactive Elements Tagging (`[data-localpilot-id]`):**
  - A client-side JavaScript routine scans the DOM for interactive, visible selectors: `<input>`, `<button>`, `<a>`, `<textarea>`, `<select>`, and `[role="button"]`.
  - **Chrome Filtering:** Navigation chrome (`<nav>`, `<header>`, `<footer>`, `.sidebar`, `.mw-sidebar`, `.navbox`, `aside`) is separated from main body elements. Elements inside the primary content area (`<main>`, `<article>`, search results, `#content`) are tagged first (`e0`, `e1`, `e2`...).
  - Up to **45 visible interactive elements** are formatted into a compact list with their tag name, type, and text label (e.g., `[e0] <a> "Sofia University (California)"`).

* **Track 2: Semantic Content Snapshot (4,500-Character Clean Window):**
  - **Why not the whole page?** Reading the entire page causes CPU lag and pushes the 3B model into context degradation.
  - **Prioritizing `<main>` and `<article>`:** Rather than scanning `<body>` from index 0 (which is always congested with header boilerplate like *"Skip to content"*, navigation bars, and cookie notices), the extractor checks for standard semantic containers (`<main>` or `<article>`).
  - **4,500-Character Clean Window (~900–1,100 tokens):** The text is stripped of multiple whitespace/blank lines and truncated to 4,500 characters. This processes in **2–2.5 seconds on CPU** and provides complete visibility across article infoboxes, lead sections, and the first 3–4 paragraphs without getting truncated by notice banners.
  - **Purpose:** The snippet gives Qwen the **semantic context** to answer the question, while the element list provides the **action handles** to navigate.

### 3. How Does the Agent Move from One State to Another (The ReAct Loop)?
At each step, Qwen receives:
* The current page URL.
* The previous 3 actions from execution history.
* The list of up to 45 tagged interactive elements (content-first).
* The 4,500-character content snapshot.

The model returns **exactly one JSON action**:
1. `{"action": "navigate", "url": "https://..."}` — Jumps to a new URL.
2. `{"action": "click", "element_id": "e0"}` — Clicks an interactive element.
3. `{"action": "type", "element_id": "e1", "text": "...", "press_enter": true}` — Fills an input.
4. `{"action": "finish", "answer": "..."}` — Completes the task with findings.

#### Action Validation & Self-Healing:
* **Editable Tag Guardrails:** Typing is only allowed into `<input>`, `<textarea>` or `contenteditable` elements, and never into password fields. A `"type"` action on a link or button is blocked; it is *not* converted into a click, because that would skip the approval gate.
* **Per-Action Exception Shields:** Every individual action (`click`, `type`, `navigate`) is wrapped in isolated `try...except` error handlers. If an element detaches or a navigation times out, the failure is appended to `history` and the loop continues, allowing the model to recover on the next step.
* **Early Finish Detection:** If the answer to the task is already visible in the snippet or element labels, Qwen is instructed to trigger `"finish"` immediately without unnecessary navigation.
* **Search Results Page Guardrail:** On search engine or result index pages (URLs containing `/search`, `?search=`, `?q=`), Qwen is prohibited from finishing on boilerplate notices (such as Wikipedia's *"The page does not exist"* notice). Instead, it must click the most relevant search result link.

### 4. Human-in-the-Loop (HITL) Remote Guidance
While the browser runs on your desktop, your Telegram card updates in real-time with step counters and Qwen's current action. You have direct control buttons under the card:
* **⏸️ Pause / Resume:** Pauses Playwright execution so you can manually inspect or scroll the page on your screen.
* **⬅️ Go Back:** Commands the browser to perform a `history.back()`, useful if the model clicked an unwanted link.
* **🛑 Stop Agent:** Immediately aborts the loop and releases browser control.
* **✅ Close Browser / 🖥️ Keep Open:** Post-completion options allowing you to inspect the final state or close Chromium.

### 5. Approval Gate for State-Changing Actions (SRS Module 3)
Every action the model proposes is validated and classified by LocalPilot's code (`action_policy.py`), not by the model:

| Category | Examples | What happens |
| :--- | :--- | :--- |
| **Read-only** | `navigate` to an http(s) URL, clicking a normal link, typing a query into a search box, `finish` | Runs immediately. |
| **State-changing** | Clicking a button or a JavaScript link, typing into any other form field | Policy checks, then pauses for your approval in Telegram. |
| **Blocked** | `javascript:`/`file:`/`chrome:` URLs, password fields, unknown element IDs, unknown actions | Never runs. The model is told it was blocked. |

**Policy checks before approval is requested** (all must pass):
1. The website is in `LOCALPILOT_ALLOWED_SITES` (empty by default, which blocks all state-changing actions).
2. The action details are complete (known website, labelled target element, text to type).
3. Purchases (buttons such as *Buy*, *Checkout*, *Place order*) state an amount within `LOCALPILOT_SPEND_LIMIT` (0 by default, which blocks all purchases) in `LOCALPILOT_CURRENCY`. The amount is reported by the model, so check it against the page before approving.

**Approval rules** (`approval_gate.py`): each request has a unique ID, belongs to your Telegram user ID, stores a fingerprint of the exact action, and records creation time, a 30-minute expiry and a used/unused status. An approval is accepted only once, only from you, and only before it expires. Right before execution the agent re-reads the element on the live page; if anything changed since you approved, the action is cancelled. Rejecting, letting it expire, or pressing 🛑 Stop cancels the action and ends the task.

**Prompt-injection protection:** page text, element labels and URLs are passed to the model inside an `<<<UNTRUSTED_WEB_CONTENT>>>` fence, and the system prompt tells the model never to follow instructions found there. Even if a page convinces the model, the model has no way to approve or skip the gate, because classification and approval are enforced outside it.

**Secrets:** every prompt goes through one function that redacts passwords, tokens, API keys and card numbers before Ollama sees them. Form-field values (which may hold autofilled passwords) are never read from the page, and typed text is not written to the log.

### 6. Persistent Browser Context & Curated Login Recipes (Module 3)
To enable real-world tasks on authenticated services without requiring repeated logins or re-triggering 2FA on every agent run, LocalPilot uses **persistent browser context caching**:
* **On-Disk Profile Storage (`vault/browser_profile/`):** Launched via Playwright `launch_persistent_context`. Stored cookies, local storage, and session tokens remain on your local disk across runs and are strictly git-ignored to prevent credential leaks.
* **Curated Login Recipes (`login_recipes.py`):** Deterministic selectors and flow descriptors for key target platforms:
  * **Amazon (`amazon.com`):** Two-step login flow (`#ap_email` -> `#continue` -> `#ap_password` -> `#signInSubmit`) with OTP/MFA detection (`#auth-mfa-otpcode`) and CAPTCHA image recognition.
  * **GitHub (`github.com`):** Single-step authentication with OctoCaptcha / ArkoseLabs detection and TOTP authenticator prompt detection.
  * **Reddit (`reddit.com`):** Single-step authentication with reCAPTCHA iframe detection and 2FA OTP prompt identification.
* **404 Interception & Fallback:** If navigation lands on a broken page or returns a 404 status, LocalPilot detects the error in real time and automatically bridges to a Google Search query for the target task, allowing the agent to self-heal.

### 7. Zero-Shot Intent Decomposition & Search Page Guardrails
To prevent complex conversational phrasing from corrupting search queries or stalling navigation:
* **Pre-Flight Intent Decomposition (`browser_service.py`):** Before launching Chromium, local Qwen separates user instructions into `target_site`, `search_keyword`, and `extraction_goal`. Search engines receive only the clean subject or entity (e.g. `"Sofia University"`), while Qwen focuses on answering the specific question (`"Find who the president or rector is"`).
* **Direct Template Matching (`search_templates.py`):** Using `resolve_template_by_site()`, LocalPilot jumps directly to authentic search endpoints for over 100 popular services (Wikipedia, GitHub, Amazon, Google Scholar, Reddit).
* **Search Results Page Guardrail:** On pages with `/search`, `?search=`, or `?q=`, Qwen is prohibited from calling `"finish"` on notice text (such as Wikipedia's *"The page does not exist"* notice) and must click the most relevant search result link.

---

## 🧪 Running the Tests

The tests use mocks and fake data only (no Telegram, Gmail, Ollama or real browser needed):

```powershell
python -m unittest discover -v
python -m compileall -q .
pip install pip-audit ruff   # dev tools, not runtime requirements
pip-audit -r requirements.txt
ruff check .
```

---

## ❓ Frequently Asked Questions (FAQ)

#### 1. Can multiple developers use the exact same Bot Token simultaneously?
**No.** Telegram's long-polling protocol only permits **one active connection per bot token at a time**. If two computers run `python bot.py` with the same token, Telegram will terminate one with a `Conflict` error. Every developer should create their own bot handle via `@BotFather`.

#### 2. Why doesn't the Python script run directly on an Android device?
Desktop web automation (Playwright/Chromium), encrypted SQLite vaults, and local LLMs (Ollama) require desktop operating system capabilities and compute power. Android aggressively terminates background processes to save battery. The phone is intentionally designed to serve as a lightweight **remote control**, while your computer acts as the **worker**.

#### 3. What happens if an unauthorized person messages my bot?
LocalPilot checks the sender of every command, message **and button press** against `TELEGRAM_ALLOWED_USER_ID` and rejects anyone else with `⛔ Access Denied`. If the value is empty, the bot is in setup mode: it only tells people their own Telegram ID and does nothing else for anyone.

#### 4. Does my computer need to stay on?
Yes. Because LocalPilot is a local-first agent that runs private tasks on your hardware, the host machine must be on and running `bot.py` while receiving remote instructions.

#### 5. Can multiple team members share the same Google OAuth Client ID (`credentials.json`)?
**Yes.** The `credentials.json` file identifies the *application* (LocalPilot) to Google and is safe to share across your team via a private channel. Each team member goes through the OAuth flow independently using their own Google account, and each person's private session token (`token.json`) is stored only on their own local machine. No one can read another person's emails.

#### 6. How does the agent handle large, heavy web pages without running out of CPU or memory?
The agent never passes the raw HTML tree to Ollama. Instead, a lightweight JavaScript function strips out invisible nodes and separates navigation chrome (headers, navbars, sidebars) from core content, tagging up to 45 primary interactive elements (search cards, article links, inputs, buttons) with runtime IDs (`[e0]`, `[e1]`). In parallel, it queries `<main>` or `<article>` directly, filtering out cookie notices and menus.

#### 7. What is the character snippet used for? Is it 1,200 characters across the whole page or per tag?
The snippet is a 4,500-character plain text window extracted specifically from the core content container (`<main>` or `<article>`). It represents the primary information on the screen (~900–1,100 tokens), covering infoboxes, lead sections, and the first 3–4 paragraphs. It gives the model semantic visibility to answer the prompt directly, while the element list provides the handles for clicking or typing.

#### 8. Can the agent complete tasks in fewer steps if the answer is found early?
**Yes.** On every iteration of the ReAct loop, Qwen evaluates whether the goal has already been satisfied. If the target answer is visible in the `<main>` snippet or in the element labels (e.g. `[e14] <a> "Repositories 20"`), Qwen returns `{"action": "finish", "answer": "..."}` immediately without navigating further. If max steps (10) are reached, a synthesis prompt extracts the best possible answer from the final page.

#### 9. Why not use OpenAPI/Swagger specs to discover search parameters?
OpenAPI (`openapi.json`) is designed for developer-facing REST APIs (like Stripe or `api.github.com`), whereas consumer websites (Google Scholar, Amazon, university sites) do not publish OpenAPI specs for human-facing web searches. Instead, LocalPilot uses a **hybrid architecture**: it maintains an authentic 100+ site parameter registry in `search_templates.py` for deterministic fast-paths, and falls back to autonomous HTML search input discovery (`[e0] <input>`) for unlisted sites.


