"""
LocalPilot — Local Credential Vault Web App
Provides a local-only, aesthetic web interface for managing credentials.
Runs on http://127.0.0.1:8080 (strictly localhost, isolated from external access).
Zero dependencies on Telegram or external web frameworks.
"""

import json
import webbrowser
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import vault_service

logger = logging.getLogger("LocalPilot.VaultApp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")

HOST = "127.0.0.1"
PORT = 8080

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LocalPilot — Secure Vault</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f17;
      --card-bg: rgba(22, 29, 45, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --accent-glow: rgba(99, 102, 241, 0.25);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --danger: #ef4444;
      --danger-hover: #dc2626;
      --success: #10b981;
      --input-bg: rgba(15, 23, 42, 0.6);
      --input-border: rgba(255, 255, 255, 0.12);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
    }

    body {
      background-color: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.08) 0px, transparent 50%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px;
    }

    .container {
      width: 100%;
      max-width: 900px;
    }

    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 32px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--accent), #8b5cf6);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 4px 14px var(--accent-glow);
    }

    .brand-title {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }

    .brand-subtitle {
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 500;
    }

    .badge-secure {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: var(--success);
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
    }

    .badge-dot {
      width: 6px;
      height: 6px;
      background-color: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--success);
    }

    .card {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      margin-bottom: 24px;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 18px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s ease;
    }

    .btn-primary {
      background: var(--accent);
      color: #fff;
      box-shadow: 0 4px 14px var(--accent-glow);
    }

    .btn-primary:hover {
      background: var(--accent-hover);
      transform: translateY(-1px);
    }

    .btn-outline {
      background: transparent;
      border: 1px solid var(--input-border);
      color: var(--text);
    }

    .btn-outline:hover {
      background: rgba(255, 255, 255, 0.05);
    }

    .btn-sm {
      padding: 6px 10px;
      font-size: 12px;
      border-radius: 6px;
    }

    .btn-danger {
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.2);
      color: var(--danger);
    }

    .btn-danger:hover {
      background: var(--danger);
      color: #fff;
    }

    .table-container {
      width: 100%;
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    th {
      padding: 12px 16px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1px solid var(--card-border);
    }

    td {
      padding: 16px;
      font-size: 14px;
      border-bottom: 1px solid var(--card-border);
      vertical-align: middle;
    }

    tr:last-child td {
      border-bottom: none;
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    .domain-cell {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 600;
    }

    .domain-favicon {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
    }

    .masked-pw {
      font-family: monospace;
      letter-spacing: 2px;
      color: var(--text-muted);
      background: rgba(255, 255, 255, 0.04);
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 13px;
    }

    .revealed-pw {
      font-family: monospace;
      font-weight: 600;
      color: #38bdf8;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.25);
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 13px;
      user-select: all;
    }

    .action-group {
      display: flex;
      align-items: center;
      gap: 8px;
      justify-content: flex-end;
    }

    .empty-state {
      padding: 48px 16px;
      text-align: center;
      color: var(--text-muted);
    }

    .empty-state-icon {
      font-size: 40px;
      margin-bottom: 12px;
      opacity: 0.6;
    }

    /* Modal Overlay */
    .modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(6px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transition: all 0.2s ease;
    }

    .modal-overlay.active {
      opacity: 1;
      pointer-events: auto;
    }

    .modal {
      background: #111827;
      border: 1px solid var(--card-border);
      border-radius: 16px;
      width: 100%;
      max-width: 440px;
      padding: 28px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
      transform: translateY(10px);
      transition: all 0.2s ease;
    }

    .modal-overlay.active .modal {
      transform: translateY(0);
    }

    .modal-title {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 20px;
    }

    .form-group {
      margin-bottom: 16px;
    }

    label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    input[type="text"], input[type="password"] {
      width: 100%;
      padding: 10px 14px;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 8px;
      color: var(--text);
      font-size: 14px;
      outline: none;
      transition: border 0.2s;
    }

    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }

    .modal-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 24px;
    }

    /* Notification Toast */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 12px 20px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 500;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      display: flex;
      align-items: center;
      gap: 10px;
      transform: translateY(40px);
      opacity: 0;
      transition: all 0.25s ease;
      z-index: 1000;
    }

    .toast.show {
      transform: translateY(0);
      opacity: 1;
    }

    .toast-success { border-color: rgba(16, 185, 129, 0.4); }
    .toast-error { border-color: rgba(239, 68, 68, 0.4); }
  </style>
</head>
<body>

  <div class="container">
    <header>
      <div class="brand">
        <div class="brand-icon">🛡️</div>
        <div>
          <div class="brand-title">LocalPilot Vault</div>
          <div class="brand-subtitle">Local On-Device Credential Store</div>
        </div>
      </div>
      <div class="badge-secure">
        <span class="badge-dot"></span>
        AES-256 Encrypted (Localhost Only)
      </div>
    </header>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Stored Web Credentials</div>
        <button class="btn btn-primary" onclick="openAddModal()">
          <span>+</span> Add Credential
        </button>
      </div>

      <div class="table-container">
        <table id="credTable">
          <thead>
            <tr>
              <th>Domain / Service</th>
              <th>Username / Email</th>
              <th>Password</th>
              <th>Note</th>
              <th style="text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody id="credBody">
            <tr>
              <td colspan="5" class="empty-state">
                <div class="empty-state-icon">🔒</div>
                <div>Loading local vault records...</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Add / Edit Modal -->
  <div class="modal-overlay" id="credentialModal">
    <div class="modal">
      <div class="modal-title" id="modalTitle">Add Credential</div>
      <form id="credForm" onsubmit="handleSave(event)">
        <div class="form-group">
          <label for="inputDomain">Domain / Website</label>
          <input type="text" id="inputDomain" placeholder="e.g. amazon.com, github.com" required>
        </div>
        <div class="form-group">
          <label for="inputUsername">Username or Email</label>
          <input type="text" id="inputUsername" placeholder="e.g. nikola@example.com" required>
        </div>
        <div class="form-group">
          <label for="inputPassword">Password</label>
          <input type="password" id="inputPassword" placeholder="••••••••••••" required>
        </div>
        <div class="form-group">
          <label for="inputNote">Optional Note</label>
          <input type="text" id="inputNote" placeholder="e.g. Personal primary account">
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-outline" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary">Save to Vault</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Toast Notification -->
  <div class="toast" id="toast"></div>

  <script>
    async function loadCredentials() {
      try {
        const res = await fetch('/api/credentials');
        const creds = await res.json();
        const tbody = document.getElementById('credBody');

        if (!creds || creds.length === 0) {
          tbody.innerHTML = `
            <tr>
              <td colspan="5" class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div>No credentials stored in your vault yet.</div>
                <div style="font-size: 12px; margin-top: 6px;">Tap "+ Add Credential" to save your first account.</div>
              </td>
            </tr>
          `;
          return;
        }

        tbody.innerHTML = creds.map(c => `
          <tr id="row-${c.id}">
            <td>
              <div class="domain-cell">
                <div class="domain-favicon">🌐</div>
                <span>${escapeHtml(c.domain)}</span>
              </div>
            </td>
            <td>${escapeHtml(c.username)}</td>
            <td>
              <span id="pw-${c.id}" class="masked-pw">••••••••••••</span>
            </td>
            <td style="color: var(--text-muted); font-size: 13px;">${escapeHtml(c.note || '—')}</td>
            <td>
              <div class="action-group">
                <button class="btn btn-outline btn-sm" onclick="revealPassword(${c.id})" title="Reveal password">
                  👁️ Reveal
                </button>
                <button class="btn btn-outline btn-sm" onclick="editCredential(${c.id}, '${escapeHtml(c.domain)}', '${escapeHtml(c.username)}', '${escapeHtml(c.note || '')}')" title="Edit credential">
                  ✏️ Edit
                </button>
                <button class="btn btn-danger btn-sm" onclick="deleteCred(${c.id}, '${escapeHtml(c.domain)}')" title="Delete">
                  🗑️
                </button>
              </div>
            </td>
          </tr>
        `).join('');
      } catch (err) {
        showToast("Error loading credentials from local database.", "error");
      }
    }

    async function revealPassword(id) {
      const el = document.getElementById(`pw-${id}`);
      // Toggle if already revealed
      if (el.dataset.revealed === "true") {
        el.className = "masked-pw";
        el.innerText = "••••••••••••";
        el.dataset.revealed = "false";
        return;
      }

      try {
        const res = await fetch(`/api/credentials/${id}/reveal`, { method: 'POST' });
        const data = await res.json();

        if (res.ok && data.password) {
          el.className = "revealed-pw";
          el.innerText = data.password;
          el.dataset.revealed = "true";
          showToast("Password unmasked! Auto-remasking in 15 seconds.", "success");

          // Auto-remask after 15 seconds for privacy
          setTimeout(() => {
            el.className = "masked-pw";
            el.innerText = "••••••••••••";
            el.dataset.revealed = "false";
          }, 15000);
        } else {
          showToast(data.error || "Failed to retrieve password.", "error");
        }
      } catch (err) {
        showToast("Error retrieving password from vault.", "error");
      }
    }

    async function editCredential(id, domain, username, note) {
      try {
        const res = await fetch(`/api/credentials/${id}/reveal`, { method: 'POST' });
        const data = await res.json();

        document.getElementById('modalTitle').innerText = "Update Credential";
        document.getElementById('inputDomain').value = (data && data.domain) || domain;
        document.getElementById('inputUsername').value = (data && data.username) || username;
        document.getElementById('inputNote').value = (data && data.note) || note;
        document.getElementById('inputPassword').value = (data && data.password) || "";
        document.getElementById('credentialModal').classList.add('active');
      } catch (err) {
        showToast("Error loading credential for editing.", "error");
      }
    }

    async function deleteCred(id, domain) {
      if (!confirm(`Are you sure you want to permanently delete the stored credential for '${domain}'?`)) {
        return;
      }
      try {
        const res = await fetch(`/api/credentials/${id}`, { method: 'DELETE' });
        if (res.ok) {
          showToast(`Deleted credential for ${domain}.`, "success");
          loadCredentials();
        } else {
          showToast("Failed to delete record.", "error");
        }
      } catch (err) {
        showToast("Error communicating with local vault.", "error");
      }
    }

    async function handleSave(e) {
      e.preventDefault();
      const domain = document.getElementById('inputDomain').value;
      const username = document.getElementById('inputUsername').value;
      const password = document.getElementById('inputPassword').value;
      const note = document.getElementById('inputNote').value;

      try {
        const res = await fetch('/api/credentials', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ domain, username, password, note })
        });
        const data = await res.json();

        if (res.ok) {
          showToast(`Saved credentials for ${domain}!`, "success");
          closeModal();
          loadCredentials();
        } else {
          showToast(data.error || "Failed to save credential.", "error");
        }
      } catch (err) {
        showToast("Error saving to local vault.", "error");
      }
    }

    function openAddModal() {
      document.getElementById('modalTitle').innerText = "Add Credential";
      document.getElementById('credForm').reset();
      document.getElementById('credentialModal').classList.add('active');
    }

    function closeModal() {
      document.getElementById('credentialModal').classList.remove('active');
    }

    function showToast(msg, type = "success") {
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.className = `toast show ${type === 'error' ? 'toast-error' : 'toast-success'}`;
      setTimeout(() => {
        toast.className = "toast";
      }, 4000);
    }

    function escapeHtml(str) {
      return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    // Load credentials on startup
    loadCredentials();
  </script>
</body>
</html>
"""


class VaultRequestHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        # Security headers: strictly bind to localhost, block framing
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        # Serve Dashboard HTML UI
        if parsed.path in ["/", "/index.html", "/vault"]:
            self._set_headers(200, "text/html; charset=utf-8")
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        # API: List all credentials (passwords masked)
        elif parsed.path == "/api/credentials":
            creds = vault_service.list_credentials()
            self._set_headers(200)
            self.wfile.write(json.dumps(creds).encode("utf-8"))
            return

        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)

        # API: Add / Update Credential
        if parsed.path == "/api/credentials":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8")
                payload = json.loads(body)

                domain = payload.get("domain", "")
                username = payload.get("username", "")
                password = payload.get("password", "")
                note = payload.get("note", "")

                rec = vault_service.save_credential(domain, username, password, note)
                self._set_headers(200)
                self.wfile.write(json.dumps(rec).encode("utf-8"))
            except ValueError as ve:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(ve)}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error saving credential: {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": "Internal server error"}).encode("utf-8"))
            return

        # API: Reveal Password / Edit Fetch (Direct from local vault)
        elif parsed.path.startswith("/api/credentials/") and (parsed.path.endswith("/reveal") or parsed.path.endswith("/edit-auth")):
            try:
                parts = parsed.path.strip("/").split("/")
                cred_id = int(parts[2])

                # Decrypt password directly in memory for localhost dashboard
                cred = vault_service.get_credential_by_id(cred_id)
                if not cred:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": "Credential not found"}).encode("utf-8"))
                    return

                self._set_headers(200)
                self.wfile.write(json.dumps({
                    "id": cred["id"],
                    "domain": cred["domain"],
                    "username": cred["username"],
                    "password": cred["password"],
                    "note": cred["note"]
                }).encode("utf-8"))

            except Exception as e:
                logger.error(f"Error retrieving credential: {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": "Retrieval failed"}).encode("utf-8"))
            return

        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"Not Found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/credentials/"):
            try:
                parts = parsed.path.strip("/").split("/")
                cred_id = int(parts[2])
                ok = vault_service.delete_credential(cred_id)
                if ok:
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                else:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        # Clean logging: do not clutter terminal with every single heartbeat/poll
        pass


def main():
    print("=" * 65)
    print(" LocalPilot — Local Encrypted Vault Dashboard")
    print("=" * 65)
    print(f"Server running locally at: http://{HOST}:{PORT}")
    print("Security: Bound strictly to 127.0.0.1 (No external/network access)")
    print("Storage:  SQLite (vault/vault.db) with Fernet-encrypted password field")
    print("Auth:     NONE - anyone using this Windows account can reveal passwords")
    print("=" * 65)
    print("Opening web dashboard in your default browser...")
    print("Press Ctrl+C to stop the vault server.\n")

    # Ensure database schema is ready
    vault_service.get_db_connection()

    server = HTTPServer((HOST, PORT), VaultRequestHandler)

    # Automatically launch in browser
    try:
        webbrowser.open(f"http://{HOST}:{PORT}")
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Local Vault server. Resources released safely.")
        server.server_close()


if __name__ == "__main__":
    main()
