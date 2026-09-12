# AgentForge

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![LLM](https://img.shields.io/badge/LLM-Gemini%20%7C%20OpenAI%20%7C%20Groq%20%7C%20OpenRouter-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

A sleek, responsive web application that turns structured project notes into a **Master Agent Prompt (BRD/FRD style)** using any cloud or local LLM Provider (Google Gemini, OpenAI, Groq, OpenRouter, or Custom OpenAI-Compatible APIs).

**Powered by SSP** — AgentForge Engine runs on the SSP platform stack.

---

## Features

* **Multi-Provider Support**: Connect to Google Gemini, OpenAI, Groq, OpenRouter, or any OpenAI-compatible API endpoint.
* **Dynamic Model Fetching**: Click **Fetch Models** to query your provider's endpoint for all available models, then select your preferred model from the dropdown.
* **Persistent Settings**: Base URL, Model Name, and API Key stored locally in SQLite (`data/config.sqlite`).
* **API Key Encryption & Masking**: API Keys are encrypted at rest (Fernet) and masked (`sk-...1234` / `AIza...WXYZ`) with an interactive **Show / Hide Eye toggle**.
* **Live Connection Testing**: Test provider API keys and endpoints directly from the UI before saving.
* **Master Prompt Generation**: High-fidelity system prompt output structured with Role, Goal, Process Steps, Review Checklist, and Output Format.
* **Prompt Library & Versioning**: Save prompts, track version families, compare versions with the Diff engine, and export to Markdown / JSON / YAML / LangChain / CrewAI.
* **Multi-Agent Orchestrator**: Generate a coordinated 3-agent (Architect / Developer / QA) prompt suite.
* **FastAPI + Modern Tailwind UI**: Clean dark mode design with micro-animations and copy-to-clipboard functionality.
* **Native App Window**: Desktop and installed versions open in their own native window via WebView2 (same full-width UI, no browser tab); falls back to the browser automatically if WebView2 is unavailable.
* **Toast Notifications**: Every success and error action across the app (sign in, sign up, generate, save, settings, library, export) surfaces as a themed slide-in toast with a progress bar — no scattered inline status text.
* **PWA (Progressive Web App)**: Installable on Android/iOS home screen via `manifest.webmanifest` + service worker + generated icons.
* **Windows EXE + Installer**: Build a standalone `AgentForge.exe` (PyInstaller) and an Inno Setup installer.

---

## Prerequisites & Requirements

Make sure you have installed all dependencies listed in `requirements.txt`:

* **Python 3.11+**
* Dependencies (`requirements.txt`):
  * `fastapi`
  * `uvicorn[standard]`
  * `httpx`
  * `jinja2`
  * `python-dotenv`
* An API Key for your preferred provider:
  * [Google Gemini API Key](https://aistudio.google.com/app/apikey) *(Recommended - Free Tier Available)*
  * [Groq API Key](https://console.groq.com/keys)
  * [OpenAI API Key](https://platform.openai.com/api-keys)
  * [OpenRouter API Key](https://openrouter.ai/keys)

---

## How to Run the Project

### 1. Clone & Navigate to Project Directory

```bash
git clone <repo-url>
cd Prompt_generation
```

### 2. Create & Activate Virtual Environment

**Windows:**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**Mac / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the Application Server

Run the launcher script:

```bash
python launch.py
```

The app opens in its own **native app window** (same design, no browser chrome). Use
`python launch.py --browser` to open in the system browser instead, or
`python launch.py --no-browser` to start the server silently without any window.

---

## Windows App & Installer

Anyone can get AgentForge on Windows by downloading and running the setup file.
After installation, AgentForge opens in its own **native app window** (powered by
WebView2) — exactly the same full-width dark interface, just without a browser tab.

### 1. Build the end-user installer (requires Inno Setup 6)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
```

This builds the app and wraps it in a complete installer. The final deliverable is:

```text
dist\installer\AgentForge-Setup.exe
```

Users simply **download → run → Next → Finish**, and AgentForge opens in its own
window. The installer includes:

* Wizard with welcome + MIT license agreement
* Start Menu icons and an Uninstall entry
* Optional desktop shortcut
* Optional "start when I sign in" (auto-starts with `--no-browser`)
* A full uninstaller

> Note: an unsigned installer may trigger Windows SmartScreen ("Windows protected your PC").
> Click **More info → Run anyway**, or purchase a code-signing certificate (OV/EV, paid).
> On first launch the app looks for the system's WebView2 runtime (pre-installed on
> Windows 10 1903+ / Windows 11); if it is missing the app automatically falls back to
> opening your system browser.

---

## PWA (Install on Mobile & Desktop Browser)

The app also runs as a PWA for browsers that support it. It serves
`/manifest.webmanifest`, `/sw.js`, and PWA icons
(`icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `apple-touch-icon.png`).

* **Android**: open the app in Chrome → menu → **Install app**.
* **iOS**: open in Safari → Share → **Add to Home Screen**.
* **Windows**: Chrome/Edge → the install icon in the address bar → **Install**.
* Mobile install generally requires **HTTPS**: use a tunnel (ngrok/cloudflare) or a reverse
  proxy with a valid certificate; `http://localhost` also works during local testing.
* Service workers are network-first for `/api/*` so no stale responses or cached secrets are served offline.

---

## Configuring Your LLM Provider in the UI

1. Open `http://127.0.0.1:8765` in your browser.
2. Click the **LLM Provider** button in the header.
3. Select a **Provider Preset** (or enter a custom Base URL).
4. Enter your **API Key** (use the eye icon to toggle visibility).
5. Click **Fetch Models** to automatically load all available models from that provider into the dropdown menu.
6. Select your desired model from the dropdown (or type it manually).
7. Click **Test Connection** to verify your setup.
8. Click **Save Settings**. Your API key will now be stored masked and encrypted locally!

---

## Project Structure

```text
Prompt_generation/
│
├── launch.py                  # Server launcher (auto-picks free port)
├── pg_ui/
│   ├── app.py                # FastAPI backend, auth middleware & API routes
│   ├── static/               # favicon/.ico, manifest.webmanifest, sw.js, PWA icons
│   └── templates/
│       ├── index.html        # Responsive Tailwind UI & Provider Modal (toast notifications)
│       ├── login.html        # Themed Sign In page (multi-user / password modes)
│       └── signup.html       # Themed account registration page
├── prompt_generation/
│   ├── builder.py            # Prompt builder logic
│   ├── config.py             # Server configuration (PORT / HOST / auth / writable dir)
│   ├── db.py                 # SQLite database, key encryption & masking
│   ├── llm_client.py         # Universal OpenAI-compatible LLM client (w/ retry + SSRF guard)
│   ├── orchestrator.py       # Multi-agent suite generator
│   ├── diff_engine.py        # Prompt version diff engine
│   ├── exporter.py           # Multi-format export (Markdown/JSON/YAML/LangChain/CrewAI)
│   └── ratelimit.py          # In-memory rate limiting for sensitive routes
├── tests/                    # pytest test suite (run with `pip install -r requirements.txt`)
├── scripts/
│   ├── build_exe.ps1         # PyInstaller onefile build for dist\AgentForge.exe
│   └── build_installer.ps1   # One-click: build exe + wrap in AgentForge-Setup.exe
├── installer/
│   ├── AgentForge.iss        # Inno Setup installer recipe (full end-user installer)
│   └── LICENSE.txt           # MIT license shown on the installer's license page
├── tools/
│   └── make_icons.py         # Generates favicon/PWA icons from the CPU logo (Pillow)
├── data/
│   ├── config.sqlite         # Local SQLite settings database (gitignored)
│   └── canonical_prompt_structure.md
├── requirements.txt          # Everything: runtime + icon tooling + dev/test deps
├── Dockerfile                # Server deployment (auto-installs requirements.txt)
└── .env
```

---

## Security Notes

* The app **binds to `127.0.0.1` by default** (`HOST` in `.env`). Set `HOST=0.0.0.0` **only** if you explicitly need LAN access.
* API keys are **encrypted at rest** using `cryptography` (Fernet) with a machine-local key in `data/.secret_key`. The legacy SQLite stores were plaintext; existing keys remain readable and are re-encrypted on the next settings save.
* **Per-user data isolation**: prompts are scoped to the signed-in account and the
  isolation is enforced in the database layer (not just the UI) — an account can
  never list, read, version, diff or delete another account's prompts. APIs to
  another user's prompt simply behave like a missing record.
* **No data auto-deletion**: prompts and their full date/time history stay until
  the owning user deletes them. Updating the app or uninstalling it **never**
  touches runtime data — everything lives in `data/config.sqlite` next to the app
  (e.g. `%LOCALAPPDATA%\Programs\AgentForge\data`), outside the installer's file list.
* **Login required everywhere**: auth is **ON by default** — local, installed, or deployed,
  the app opens on a themed **Sign In** page and visitors **register their own account**
  (username + password, PBKDF2-hashed, stored in `data/config.sqlite`) before use. Sessions use
  an HTTP-only signed cookie (30 days) with a **Sign Out** button in the header, and the whole
  app (UI, `/api/*`, static assets) is protected.
* **Switch modes via `.env`**: set `APP_AUTH_TOKEN=<password>` for a single shared password mode
  (the same value also works as `Authorization: Bearer <token>` for API clients), or
  `APP_AUTH_USERS=1` to keep the default multi-user registration + login. Set `APP_AUTH_OFF=1`
  to disable login entirely for rapid local debugging.
* Costly routes (`/api/generate`, `/api/orchestrate`, `/api/models/fetch`, `/api/settings/test`) are rate-limited in memory (20 requests / 60s per IP).
* `/api/health` performs **no** LLM calls, so it is safe to poll from the UI.
* **SSRF guard**: API keys are sent only to public hosts; connecting to private/LAN
  addresses is blocked unless you set `AGENTFORGE_ALLOW_LOCAL_LLM=1` (e.g. a LAN Ollama/LM Studio server).
* **XSS hardening**: user/LLM-supplied text rendered into library and orchestrator cards is HTML-escaped in the UI.

---

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests -q
```

---

## API Endpoints

### Get Provider Settings
```http
GET /api/settings
```

### Save Provider Settings
```http
POST /api/settings
```

### Fetch Available Models
```http
POST /api/models/fetch
```

### Test Connection
```http
POST /api/settings/test
```

### Generate Master Prompt
```http
POST /api/generate
```

---

## Deployment (Free → Paid)

Need to host AgentForge online? See **[DEPLOYMENT.md](DEPLOYMENT.md)** — a complete
guide covering **free tiers** (Render, Oracle Cloud "Always Free"), **cheap paid
VPS** hosting (DigitalOcean / Hostinger), Docker + Caddy HTTPS, persistent-data
backups, and the production security checklist.

---

## License

This project is licensed under the MIT License.
