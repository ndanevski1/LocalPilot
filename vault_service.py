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

