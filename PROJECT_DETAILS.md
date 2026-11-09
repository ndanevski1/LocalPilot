# LocalPilot — On-Device Personal Action Agent

[![GitHub Repository](https://img.shields.io/badge/GitHub-ndanevski1%2FLocalPilot-blue?style=flat-square&logo=github)](https://github.com/ndanevski1/LocalPilot)
![Project Phase](https://img.shields.io/badge/Phase-Prototype-yellow?style=flat-square)

LocalPilot is an open-source, local-first autonomous AI action agent that runs directly on your computer to handle digital chores—such as compiling email digests and managing web purchases—while keeping private credentials and session data encrypted strictly on your host hardware.

---

## 👥 Team & Roles

* **Project Manager / Leader:** Mounika Kannan
* **Assistant Project Manager / Software Engineer:** Nikola Danevski
* **Software Engineer / UI/UX Designer:** Daniiar Gadeev
* **Quality Assurance & Documentation:** Sowjanya Sai Lakshmi Pothana

---

## 🌟 Key Features (target design)

> The list below is the target design. See **Implementation Status** further down and the README's *Feature Status* section for what the code does today.

* **Zero-Trust Password Masking:** Raw credentials never reach LLMs. The agent processes DOM trees with synthetic placeholder tokens (e.g., `{{AMAZON_PASSWORD}}`) and injects real credentials locally. *(Partly implemented: secrets are redacted from prompts and field values are never read; placeholder tokens and local injection are planned.)*
* **Human-in-the-Loop (HITL) Gatekeeper:** All state-changing or financial actions (e.g., placing purchases, sending emails) automatically pause for direct approval via Telegram interactive buttons. *(Implemented for the browser agent.)*
* **Seamless Telegram Remote Control:** Trigger tasks, monitor live execution steps, and review screenshots remotely through an outbound Telegram bot connection without open ports or router configuration. *(Implemented except screenshots.)*
* **Automated Inbox Summaries:** Fetches and synthesizes unread emails into clean daily digests via direct local OAuth integrations (e.g., Gmail REST API). *(Implemented: read-only digest of the 5 latest unread Primary emails.)*
* **Semantic Web Automation:** Uses Playwright paired with accessibility tree processing (`browser-use`), enabling the agent to navigate e-commerce stores dynamically without relying on brittle CSS selectors. *(Partly implemented: Playwright with a custom DOM element extractor; `browser-use` and ARIA trees are not used.)*

---

## 🏗️ System Architecture

LocalPilot operates as a background daemon process on the user's host machine. Remote interaction occurs over outbound HTTPS connections via the Telegram Bot API.

> **Current implementation:** the daemon is a plain Python process using `python-telegram-bot` long-polling (no FastAPI or WebSockets yet), and only the local Ollama model is used (no hybrid router yet). The diagram below shows the target architecture.

```
┌───────────────────────────────────────────────────────────┐
│                      User Mobile Device                   │
│                    (Telegram App UI / Bot)                │
└─────────────────────────────┬─────────────────────────────┘
                              │ Telegram API (Outbound HTTPS)
                              ▼
┌───────────────────────────────────────────────────────────┐
│ Host Computer (LocalPilot FastAPI Daemon)                 │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────┐ │
│  │ Local Vault      │  │ Hybrid LLM        │  │ HITL     │ │
│  │ (Encrypted Keys) │  │ Router           │  │ Gate     │ │
│  └────────┬─────────┘  └────────┬─────────┘  └────┬─────┘ │
│           │                     │                 │       │
│           ▼                     ▼                 ▼       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────┐ │
│  │ Gmail REST API   │  │ Playwright Engine│  │ Desktop  │ │
│  │ (Service Runner) │  │ (Accessibility)  │  │ Browser  │ │
│  └──────────────────┘  └──────────────────┘  └──────────┘ │
└───────────────────────────────────────────────────────────┘
```

---

## 📜 Software Requirements Specification (SRS)

All functional requirements below follow the **Easy Approach to Requirements Syntax (EARS)** standard:

### Module 1: Credential Vault & Privacy
* **[UBIQUITOUS]** The LocalPilot system shall store all third-party login credentials, API keys, and session tokens in an encrypted local database using AES-256 encryption.
* **[EVENT-DRIVEN]** WHEN passing web page context or DOM structures to external LLM services, the LocalPilot system shall replace raw password strings and sensitive form fields with synthetic placeholder tokens.
* **[EVENT-DRIVEN]** WHEN populating authentication forms in a live browser session, the LocalPilot system shall inject decrypted credentials directly into browser DOM fields on the local host machine.

### Module 2: Remote Telegram Interface
* **[UBIQUITOUS]** The LocalPilot system shall maintain an outbound secure connection to the Telegram Bot API for remote interaction.
* **[EVENT-DRIVEN]** WHEN an authorized user submits a command via Telegram, the LocalPilot system shall parse the intent and initiate the corresponding workflow.
* **[EVENT-DRIVEN]** WHEN task execution status changes, the LocalPilot system shall transmit real-time progress logs, order summaries, and captured screenshots to the authorized Telegram chat.

### Module 3: Human-in-the-Loop (HITL) Gatekeeper
* **[STATE-DRIVEN]** WHILE executing a workflow, the LocalPilot system shall classify every tool action as either a *Read-Only* operation or a *State-Changing* operation.
* **[EVENT-DRIVEN]** WHEN a State-Changing operation is requested by the agent loop, the LocalPilot system shall pause execution and send an approval request containing an action summary and interactive confirmation buttons to Telegram.
* **[EVENT-DRIVEN]** WHEN an explicit "Approve" response is received from the authorized user, the LocalPilot system shall resume execution of the paused operation.
* **[UNWANTED / EVENT-DRIVEN]** IF an "Approve" response is not received within 30 minutes, THEN the LocalPilot system shall abort the pending operation and notify the user.

### Module 4: Web & Email Execution Engine
* **[EVENT-DRIVEN]** WHEN automating web browser tasks, the LocalPilot system shall convert raw page HTML into standardized ARIA accessibility trees before sending structured representations to the reasoning engine.
* **[EVENT-DRIVEN]** WHEN instructed to process email activity, the LocalPilot system shall retrieve unread messages using the Gmail REST API and synthesize a structured summary digest.

### Module 5: Hybrid Model Routing
* **[EVENT-DRIVEN]** WHEN processing text classification, email filtering, or simple intent parsing, the LocalPilot system shall route requests to local on-device models.
* **[EVENT-DRIVEN]** WHEN performing complex visual web navigation or multi-step reasoning, the LocalPilot system shall route requests to high-capability cloud LLM APIs.

---

## 📋 Implementation Status

| SRS item | Status | Notes |
| :--- | :--- | :--- |
| M1: AES-256 encrypted credential store | ⚠️ Partial | SQLite + Fernet (AES-128-CBC + HMAC) on the password column only; key stored in `vault/.vault_key`. Not SQLCipher, not AES-256. |
| M1: Placeholder tokens instead of raw secrets in LLM context | ⚠️ Partial | Secrets are redacted from every prompt and form-field values are never read; placeholder tokens are not implemented. |
| M1: Local credential injection | ❌ Planned | The browser agent does not use the vault. |
| M2: Outbound Telegram connection, authorized user only | ✅ Implemented | Every command, message and button press is re-authenticated; setup mode is locked down. |
| M2: Real-time progress logs | ✅ Implemented | Live progress card with Pause / Go Back / Stop. |
| M2: Order summaries and screenshots | ❌ Planned | |
| M3: Classify every action as read-only or state-changing | ✅ Implemented | Browser agent actions (`action_policy.py`). |
| M3: Pause state-changing actions for Telegram approval | ✅ Implemented | With website allow-list, spending limit and completeness checks. |
| M3: Resume only on explicit approval from the authorized user | ✅ Implemented | Single-use approvals bound to user ID and exact action (`approval_gate.py`). |
| M3: Abort after 30 minutes without approval | ✅ Implemented | Card is updated and the action cancelled. |
| M4: ARIA accessibility trees | ❌ Planned | A custom DOM element extractor is used instead. |
| M4: Gmail unread digest | ✅ Implemented | Read-only scope. |
| M5: Hybrid local / cloud model routing | ❌ Planned | Only local Ollama (`qwen2.5:3b`). |
| Vault: Windows PIN before revealing passwords | ❌ Planned | The dashboard reveals passwords without extra authentication. |

`/demo_hitl` is a **simulation** of a purchase approval: it uses the real approval gate, but nothing is bought and no credentials are used.

---

## 🛠️ Planned Tech Stack

> Target stack. Currently in use: Python, `python-telegram-bot`, Playwright, Ollama (`qwen2.5:3b`), Gmail REST API, SQLite + `cryptography` (Fernet).

| Component | Technology |
| :--- | :--- |
| **Backend Core** | Python 3.12+, FastAPI, WebSockets |
| **Browser Automation** | Playwright, `browser-use` |
| **LLM Orchestration** | LiteLLM / PydanticAI (Claude 3.5 Sonnet / GPT-4o for web, Ollama for offline) |
| **Integrations** | Telegram Bot API, Gmail REST API (Google OAuth 2.0) |
| **Vault & Storage** | SQLite encrypted with SQLCipher (AES-256) |

---

## 🛡️ Risk Mitigation Strategy

| Challenge | Impact | Mitigation Protocol |
| :--- | :--- | :--- |
| **Bot Detection / CAPTCHAs** | Execution loop hangs or fails when encountering challenge screens. | **Pause-and-Handoff:** LocalPilot pauses execution, alerts Telegram, and leaves the browser open on your desktop so you can complete the CAPTCHA manually. |
| **E-Commerce Layout Changes** | Dynamic updates break hardcoded CSS/XPath scripts. | **Accessibility Trees:** Navigates standard ARIA accessibility trees rather than hardcoded DOM selectors. |
| **Scope Creep** | Delayed delivery due to broad site support. | **Focused Target Scope:** Prototype support is explicitly constrained to 2–3 major web vendors for initial launch. |

---

## 🔗 Repository & Project Status

* **Official Repository:** [https://github.com/ndanevski1/LocalPilot](https://github.com/ndanevski1/LocalPilot)
* **Current Phase:** Prototype. The Telegram bot, Gmail digest, browser agent with approval gate, and local vault dashboard are implemented; see **Implementation Status** above for what remains planned.
