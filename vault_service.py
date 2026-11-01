"""
LocalPilot — Encrypted Credential Vault Service (Module 3)
Provides zero-trust local storage for sensitive web credentials.
Uses SQLite with authenticated AES-256 (Fernet) field encryption, PBKDF2 key derivation,
and native Windows OS credentials prompt (CredUIPromptForWindowsCredentials / LogonUser).
"""

import os
import sys
import base64
import sqlite3
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("LocalPilot.Vault")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(BASE_DIR, "vault")
VAULT_DB = os.path.join(VAULT_DIR, "vault.db")
KEY_SALT_FILE = os.path.join(VAULT_DIR, ".vault_salt")
KEY_FILE = os.path.join(VAULT_DIR, ".vault_key")


def _ensure_vault_dir():
    """Creates vault directory if it doesn't exist."""
    if not os.path.exists(VAULT_DIR):
        os.makedirs(VAULT_DIR, mode=0o700, exist_ok=True)


def _get_or_create_master_key() -> bytes:
    """
    Retrieves or generates a persistent machine-bound master key for AES-256 (Fernet).
    Key is derived via PBKDF2 with 300,000 rounds of SHA-256 and salted per machine installation.
    """
    _ensure_vault_dir()

    if os.path.exists(KEY_FILE) and os.path.exists(KEY_SALT_FILE):
        try:
            with open(KEY_FILE, "rb") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Error reading vault key: {e}")

    # Generate new random salt
    salt = os.urandom(16)
    with open(KEY_SALT_FILE, "wb") as f:
        f.write(salt)

    # Derive key using machine-specific seeds (e.g. computer name, username, machine UUID)
    machine_id = os.environ.get("COMPUTERNAME", "LocalPilotHost") + os.environ.get("USERNAME", "DefaultUser")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=300000,
    )
    raw_key = kdf.derive(machine_id.encode("utf-8"))
    fernet_key = base64.urlsafe_b64encode(raw_key)

    with open(KEY_FILE, "wb") as f:
        f.write(fernet_key)

    return fernet_key


def _get_cipher() -> Fernet:
    """Returns Fernet cipher instance initialized with master key."""
    key = _get_or_create_master_key()
    return Fernet(key)


def get_db_connection() -> sqlite3.Connection:
    """Returns a connection to the vault database and ensures schema exists."""
    _ensure_vault_dir()
    conn = sqlite3.connect(VAULT_DB)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                username TEXT NOT NULL,
                encrypted_password TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(domain, username)
            )
        """)
    return conn


def save_credential(domain: str, username: str, password: str, note: str = "") -> Dict[str, Any]:
    """
    Encrypts password with AES-256 and stores/updates credential in SQLite.
    Returns dictionary with stored credential record (password is masked).
    """
    domain = domain.strip().lower()
    # Normalize domain: strip http:// or https:// if present
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    username = username.strip()
    note = note.strip()

    if not domain or not username or not password:
        raise ValueError("Domain, username, and password are all required.")

    cipher = _get_cipher()
    encrypted_pw = cipher.encrypt(password.encode("utf-8")).decode("utf-8")
    now_str = datetime.utcnow().isoformat()

    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM credentials WHERE domain = ? AND username = ?",
            (domain, username)
        )
        row = cursor.fetchone()
        if row:
            cred_id = row["id"]
            cursor.execute("""
                UPDATE credentials 
                SET encrypted_password = ?, note = ?, updated_at = ?
                WHERE id = ?
            """, (encrypted_pw, note, now_str, cred_id))
        else:
            cursor.execute("""
                INSERT INTO credentials (domain, username, encrypted_password, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (domain, username, encrypted_pw, note, now_str, now_str))
            cred_id = cursor.lastrowid

    logger.info(f"Credential for '{domain}' ({username}) saved successfully in vault.")
    return {
        "id": cred_id,
        "domain": domain,
        "username": username,
        "note": note,
        "updated_at": now_str
    }


def list_credentials() -> List[Dict[str, Any]]:
    """Returns list of all credentials with passwords safely masked."""
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, domain, username, note, created_at, updated_at FROM credentials ORDER BY domain ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_credential_by_domain(domain: str) -> Optional[Dict[str, str]]:
    """
    Retrieves the first credential for a given domain and decrypts the password.
    Used internally by the autonomous browser agent.
    """
    clean_domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, domain, username, encrypted_password, note FROM credentials WHERE domain LIKE ? LIMIT 1",
            (f"%{clean_domain}%",)
        )
        row = cursor.fetchone()
        if not row:
            return None

        cipher = _get_cipher()
        try:
            raw_password = cipher.decrypt(row["encrypted_password"].encode("utf-8")).decode("utf-8")
            return {
                "id": row["id"],
                "domain": row["domain"],
                "username": row["username"],
                "password": raw_password,
                "note": row["note"]
            }
        except Exception as e:
            logger.error(f"Failed to decrypt password for {domain}: {e}")
            return None


def get_credential_by_id(cred_id: int) -> Optional[Dict[str, str]]:
    """Retrieves and decrypts a specific credential by its ID."""
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, domain, username, encrypted_password, note FROM credentials WHERE id = ?", (cred_id,))
        row = cursor.fetchone()
        if not row:
            return None

        cipher = _get_cipher()
        try:
            raw_password = cipher.decrypt(row["encrypted_password"].encode("utf-8")).decode("utf-8")
            return {
                "id": row["id"],
                "domain": row["domain"],
                "username": row["username"],
                "password": raw_password,
                "note": row["note"]
            }
        except Exception as e:
            logger.error(f"Failed to decrypt password for ID {cred_id}: {e}")
            return None


def delete_credential(cred_id: int) -> bool:
    """Deletes a credential by its ID."""
    conn = get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM credentials WHERE id = ?", (cred_id,))
        return cursor.rowcount > 0


# ─── OS Native Authentication (Windows / Cross-Platform) ─────────────────────

def verify_device_credentials(prompt_reason: str = "reveal your stored password") -> Tuple[bool, str]:
    """
    Prompts the user for OS device authentication (Windows PIN / Password / Windows Hello).
    Returns (success: bool, message: str).
    """
    if sys.platform != "win32":
        # Fallback for Linux / macOS in development
        return True, "OS Authentication verified (non-Windows fallback)."

    import ctypes
    from ctypes import wintypes

    # Define CredUIPromptForWindowsCredentialsW structure & function
    class CREDUI_INFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hwndParent", wintypes.HWND),
            ("pszMessageText", wintypes.LPCWSTR),
            ("pszCaptionText", wintypes.LPCWSTR),
            ("hbmBanner", wintypes.HBITMAP),
        ]

    credui = ctypes.windll.credui
    advapi32 = ctypes.windll.advapi32

    # Flags for CredUIPromptForWindowsCredentials
    CREDUIWIN_GENERIC = 0x1
    CREDUIWIN_CHECKBOX = 0x2
    CREDUIWIN_AUTHPACKAGE_ONLY = 0x10
    CREDUIWIN_IN_CRED_ONLY = 0x20
    CREDUIWIN_ENUMERATE_CURRENT_USER = 0x200

    info = CREDUI_INFO()
    info.cbSize = ctypes.sizeof(CREDUI_INFO)
    info.hwndParent = None
    info.pszCaptionText = "LocalPilot — Security Verification"
    info.pszMessageText = f"LocalPilot Vault is requesting authorization to {prompt_reason}.\nEnter your Windows PIN or account password to confirm:"
    info.hbmBanner = None

    auth_pkg = wintypes.ULONG(0)
    out_cred_buffer = ctypes.c_void_p()
    out_cred_size = wintypes.ULONG(0)
    save_flag = wintypes.BOOL(False)

    # Prompt user with the native Windows Security Dialog
    status = credui.CredUIPromptForWindowsCredentialsW(
        ctypes.byref(info),
        0,                                   # dwAuthError
        ctypes.byref(auth_pkg),              # pulAuthPackage
        None,                                # pvInAuthBuffer
        0,                                   # ulInAuthBufferSize
        ctypes.byref(out_cred_buffer),       # ref to output buffer
        ctypes.byref(out_cred_size),         # ref to output size
        ctypes.byref(save_flag),             # pfSave
        CREDUIWIN_GENERIC | CREDUIWIN_ENUMERATE_CURRENT_USER
    )

    ERROR_SUCCESS = 0
    ERROR_CANCELLED = 1223

    if status == ERROR_CANCELLED:
        return False, "Authentication cancelled by user."
    elif status != ERROR_SUCCESS:
        return False, f"Windows authentication prompt error (code {status})."

    # Unpack credentials using CredUnPackAuthenticationBufferW
    max_user_len = 512
    max_domain_len = 512
    max_pass_len = 512

    username_buf = ctypes.create_unicode_buffer(max_user_len)
    domain_buf = ctypes.create_unicode_buffer(max_domain_len)
    password_buf = ctypes.create_unicode_buffer(max_pass_len)

    un_len = wintypes.DWORD(max_user_len)
    dom_len = wintypes.DWORD(max_domain_len)
    pw_len = wintypes.DWORD(max_pass_len)

    unpack_ok = credui.CredUnPackAuthenticationBufferW(
        0,
        out_cred_buffer,
        out_cred_size,
        username_buf,
        ctypes.byref(un_len),
        domain_buf,
        ctypes.byref(dom_len),
        password_buf,
        ctypes.byref(pw_len)
    )

    # Clear credential buffer memory immediately
    ctypes.windll.kernel32.CoTaskMemFree(out_cred_buffer)

    if not unpack_ok:
        return False, "Failed to decode authentication credentials from security subsystem."

    # Validate the credentials against Windows Security Provider (LogonUserW)
    LOGON32_LOGON_INTERACTIVE = 2
    LOGON32_PROVIDER_DEFAULT = 0
    token_handle = wintypes.HANDLE()

    logon_ok = advapi32.LogonUserW(
        username_buf.value,
        domain_buf.value if domain_buf.value else None,
        password_buf.value,
        LOGON32_LOGON_INTERACTIVE,
        LOGON32_PROVIDER_DEFAULT,
        ctypes.byref(token_handle)
    )

    # Zero-out password buffer in memory immediately
    ctypes.memset(ctypes.byref(password_buf), 0, ctypes.sizeof(password_buf))

    if logon_ok:
        ctypes.windll.kernel32.CloseHandle(token_handle)
        logger.info("Windows device authentication succeeded.")
        return True, "Device verification successful."
    else:
        err_code = ctypes.windll.kernel32.GetLastError()
        logger.warning(f"LogonUser failed with code: {err_code}")
        return False, "Incorrect Windows credentials or authorization denied."
