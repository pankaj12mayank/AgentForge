# AgentForge v4.0 — Chat Workspace & File Parsing (A-to-Z Scope Plan)

Target: make AgentForge feel like **ChatGPT / Claude** — a chat-first workspace
where you still generate master prompts, then run them in per-project chats with
full **multi-file parsing** (images, XLSX, CSV, DOC/DOCX, PDF, TXT) powering the
conversation.

Everything below keeps the current stack: **FastAPI + vanilla JS + Tailwind +
SQLite + native window (pywebview/WebView2) + PWA + single installer**.

> **STATUS: PLAN-ONLY** — implementation has NOT started. Decisions in §9 are
> locked; nothing is built or committed until you say go.

---

## 1. Current state (v3.1 — what already exists)

| Area | Status |
|------|--------|
| Master Prompt generation (Role/Goal/Steps → Markdown) | ✅ `/api/generate` |
| 3-agent Orchestrator suite | ✅ `/api/orchestrate` |
| Prompt Library + versioning + diff + multi-format export | ✅ |
| Multi-user auth (register/login) + per-user data isolation | ✅ `prompts.username` |
| Provider settings (OpenAI-compat Base URL, fetch models, test) | ✅ |
| Native app window + browser + `--no-browser` server modes | ✅ |
| PWA (offline shell) + single EXE installer | ✅ v3.1.0 |
| **Limiters** | LLM calls are **text-only, single-turn, non-streaming**; no chat history table; no sidebar; no file uploads |

Missing for a Claude/ChatGPT feel: chat threads, projects sidebar, message
history, conversational context, streaming, markdown-rendered replies, and file
parsing.

---

## 2. Scope (Epics)

### E1 — Chat workspace (the "Claude/ChatGPT" interface)
- Chat-first home view with message bubbles (user right, assistant left).
- Multi-turn conversation: every reply sees the full history + the bound master
  prompt as system prompt → **"reply based on result"** works naturally.
- **Streaming replies** (token-by-token) for the chat feel; also a non-stream fallback.
- Message actions: **Copy**, Regenerate (⟳ re-run last answer), Edit own message,
  Download as Markdown, thumbs up/down (local only, no analytics).
- Typing indicator, "Stop generation" button, auto-scroll, Enter=send / Shift+Enter=linebreak.
- **Markdown rendering** for assistant replies (bundled `marked`, not CDN, so the
  PWA stays offline-first) + code-block copy buttons.

### E2 — Sidebar & Projects (navigation)
- Global left sidebar (like Claude/ChatGPT): **+ New Chat**, project tree,
  collapsible folders, per-chat search, per-project rename/delete/archive.
- Chat lives inside a **Project**: `Project → many Chats → many Messages`.
- Current tabs (Engineer / Orchestrator / Library / Diff) stay accessible from the
  top bar — Chat is the new default landing view.

### E3 — Prompt → Chat flow (the glue you described)
- Generated prompt → **"Send to Chat"** button → creates a chat whose **system
  prompt = that master prompt** → opens Chat view.
- Library items → "Open in Chat" (same binding).
- Orchestrator suite → "Send all 3 agents" → creates 3 chats (Architect/Developer/QA)
  in a project, so you can run each agent and reply to its results.

### E4 — Multi-file parsing (per chat, powers the replies)
Supported in v1 (whitelisted):

| Type | Ext | Parser | Output |
|------|-----|--------|--------|
| CSV / TXT / MD / LOG / JSON | .csv .txt .md .json .log | stdlib | text (truncated) |
| Excel | .xlsx | `openpyxl` (read-only) | rows → Markdown table |
| Word | .docx | `python-docx` | paragraphs + tables → text |
| PDF | .pdf | `pypdf` (text layer) | text; scanned PDFs → needs a vision model |
| Images | .png .jpg .jpeg .webp | — | **sent to the vision model as base64** (no local OCR) |
| Code | .py .js .ts .sql .html ... | stdlib | text |

Each chat's conversation context includes the extracted file content so replies
are **based on the file** (you describe: "uske base pr result chlta rhe").

### E5 — Limits & safety (must-have, not optional)
- Max **25 MB/file**, **5 files/message** (configurable env limits).
- Extracted text capped (default ~100k chars/file) with a visible
  "truncated" notice — keeps prompt tokens sane.
- Unknown/unsupported types rejected with a clear message (not a 500).
- Each parser runs isolated: one bad file never crashes the chat.
- **Legacy `.doc` is NOT supported** v1 (no reliable free parser) — tell user to
  re-save as `.docx`/`.pdf`. (Decision needed — see §9.)

---

## 3. UI/UX design (wireframe)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [≡]  AgentForge            [Chat][Engineer][Orch.][Library][Diff]   [⚙][⏻] │  top bar
├──────────────┬─────────────────────────────────────────────────────────────┤
│  + New Chat  │                                                             │
│              │  ┌────────────────────────────────────────────────────┐      │
│  PROJECTS    │  │  system prompt chip: "Master Prompt: Web App      │      │
│  ▼ Web Gen   │  │   Architect   [edit] [x attach]                   │      │
│    • Chat A  │  └────────────────────────────────────────────────────┘      │
│    • Chat B  │                                                             │
│  ▼ Marketing │      [user] Generate a landing page HTML skeleton          │
│    • Chat C  │                                                             │
│              │      [assistant]  # Landing Page                            │
│  🔍 Search   │      1. Header — nav, CTA button                            │
│  ⚙ Settings  │      2. Hero …                                             │
│    (folder   │        [Copy] [⟳] [Download]                                │
│     tree,    │                                                             │
│     rename,  │      [  attach 📎 Ask anything…                    (→) ]    │
│     delete)  │       files: pdf.pdf ✓ xlsx ✓ image.png ✓   [Stop]         │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

**States & details**
- **Empty project**: friendly empty state with 3 one-click starters
  ("Analyze my PDF", "Clean this CSV", "Explain this image").
- **Message compose**: attachment drop zone + picker; typed pre-send; paste-from-clipboard images supported.
- **Streaming**: caret cursor + assistant bubble grows live; "Stop" appears while generating.
- **Loading**: skeleton bubbles (never a full-screen spinner for chat); the existing full-screen spinner stays for Engineer generation.
- **Copy** on every assistant message (and code blocks inside it).
- **Responsive**: sidebar collapses to a drawer on <1024px (mobile PWA).
- **Theme**: reuse existing dark glass/gradient brand — zero new design language.
- **Accessibility**: keyboard nav (Esc closes sidebar/modals), aria-labels on icon buttons, focus rings.

---

## 4. Data model (SQLite — additive, auto-migrated in `init_db()` like today)

```sql
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,               -- per-user isolation (existing pattern)
  name TEXT NOT NULL, description TEXT DEFAULT '',
  archived INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_projects_uname ON projects(username, updated_at DESC);

CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL, project_id INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT 'New Chat',
  system_prompt TEXT DEFAULT '',        -- bound master prompt
  model_json TEXT DEFAULT '',           -- per-chat provider/model override
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_conv_uname ON conversations(username, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL, conversation_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user','assistant','system','error')),
  content TEXT NOT NULL, tokens_used INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_msg_conv ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL, conversation_id INTEGER NOT NULL,
  message_id INTEGER,                   -- nullable until message is sent
  filename TEXT NOT NULL, mime TEXT NOT NULL,
  kind TEXT NOT NULL,                   -- text|csv|xlsx|docx|pdf|image|code
  size_bytes INTEGER NOT NULL, storage_path TEXT NOT NULL,   -- under data/uploads/<username>/uuid.ext
  extraction_status TEXT DEFAULT 'pending',                  -- pending|ok|error|truncated
  extracted_text TEXT DEFAULT '', char_count INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_att_conv ON attachments(conversation_id, id);
```

Every query filters by `username` (same pattern as `prompts`) — isolation is
automatic and testable. Migrations are idempotent; existing DBs upgrade silently.

---

## 5. API design

```
Projects
  GET    /api/projects?search=&archived=          list own projects
  POST   /api/projects                            create
  PATCH  /api/projects/{id}                       rename / archive / description
  DELETE /api/projects/{id}                       delete project + chats + messages + files

Conversations
  GET    /api/projects/{pid}/conversations        list chats
  POST   /api/projects/{pid}/conversations        create (title, system_prompt, model_json)
  PATCH  /api/conversations/{id}                  rename / pin / attach system prompt
  DELETE /api/conversations/{id}

Messages
  GET    /api/conversations/{id}/messages         full history
  POST   /api/conversations/{id}/messages         send user msg {content, attachment_ids} → full reply
  POST   /api/conversations/{id}/stream           same but returns text/event-stream (typing effect)
  POST   /api/conversations/{id}/regenerate       re-run last assistant turn
  POST   /api/conversations/{id}/stop             cancel in-flight generation
  DELETE /api/conversations/{id}/messages/{mid}   delete one message

Attachments
  POST   /api/attachments       multipart upload (limit 5, 25 MB) → {id, kind, ok}
  GET    /api/attachments/{id}  download original (owner only)
  GET    /api/attachments/{id}/text  get extracted text (owner only)
  DELETE /api/attachments/{id}
```

All `/api/*` behind the existing auth middleware; upload endpoint gets the
rate limiter + size caps.

---

## 6. Backend architecture

```
pg_ui/
  app.py                existing routes + new router mounts (no rewrite)
  chat.py      (new)    ChatService: history building, windowing, regenerate/stop,
                        message persistence, attachment→content packing
  files.py     (new)    FileService: whitelist, size caps, storage under
                        data/uploads/<username>/<uuid>.<ext>, parser registry,
                        extraction in threadpool (asyncio.to_thread, never block loop)
  parsers/
    __init__.py         dispatch by mime/extension → parser or None
    text.py  csv.py  xlsx.py  docx.py  pdf.py     (one parser per type)
prompt_generation/
  llm_client.py         + `chat(messages, attachments, stream=False)`:
                        builds OpenAI multimodal payload
                        {"type":"text",...} + {"type":"image_url", base64}
                        non-stream returns full; stream yields SSE chunks
  db.py                 + new table CRUD (projects/conversations/messages/attachments)
```

**LLM plumbing** (the critical piece)
- New `chat()` builds the messages array from stored history + current user msg +
  attachment content. System prompt = bound master prompt (if a master prompt is
  bound to that conversation).
- **Text files**: extracted text is appended to the user message (chunked to the
  cap). **Images**: sent as `image_url` with `data:image/png;base64,...`.
- Streaming via SSE (uvicorn supports it out of the box) → DOM update per chunk.
- If provider/model changes mid-history, keep going — per-chat `model_json`
  override remembers what generated each reply.

**Prompt-to-chat flow example** (E3 backend)
`POST /api/projects/{pid}/conversations` with `system_prompt=<generated master prompt>`
+ `title` → returns conversation → front-end opens it. Orchestrator sends 3
conversations in one call (`POST /api/projects/{pid}/conversations:batch`).

---

## 7. What is NOT in scope v4.0 (keeps it shippable)

- Tool use / function calling / "agent autonomy" (that's a later v5). Here the
  master prompt *is* the instruction and the chat is where you run it.
- Voice, web browsing, real-time collaboration, multi-model routing.
- Local OCR (tesseract). Image understanding rides on the provider's vision model
  (Gemini / GPT-4o / Llama vision). Scanned/photo PDFs therefore need a
  vision-capable model too.
- `.doc` and `.odt` v1. (Decision needed.)
- Notifications, desktop tray, global shortcut. (Nice-to-haves.)

---

## 8. Risks register (likelihood × impact → mitigation)

| # | Risk | L | I | Mitigation |
|---|------|---|---|------------|
| R1 | Vision model not capable of images → upload succeeds, reply errors | M | M | Pre-check capability flag per provider; friendly error: "Provider model doesn't support images"; allow text-only retry with "couldn't read image" note |
| R2 | Huge file → token budget blown / slow | M | H | caps (25 MB, 100k chars), chunking, truncation notice, streaming progress |
| R3 | Malicious uploads (zip bomb via .xlsx, path traversal, macros) | L | H | never execute docs; whitelist extensions+mime; uuid storage names; macro-bearing .docx parsed text-only (macros never run); extract in isolation |
| R4 | Private data sent to external LLM (user pastes sensitive files) | M | M | existing SSRF guard + warning banner when attachments contain sensitive types; per-user storage; delete-able files |
| R5 | Exe/installer grows (openpyxl+pypdf+docx+PIL ≈ +10–15 MB) and PyInstaller build time/memory | M | M | lean libs only (no pandas), hidden-imports list added, verify `--on `noconsole` build still ≤ ~50 MB |
| R6 | Multi-turn context window overflow | M | M | history windowing (e.g. last N messages + system prompt; earlier summary optional v1) |
| R7 | Streaming + in-memory rate limiter (single instance only) | L | M | re-note in DEPLOYMENT.md: keep 1 worker/1 container |
| R8 | Parser crashes (malformed PDF/XLSX) | M | M | per-parser try/except → attachment marked `error`, chat continues |
| R9 | Sidebar/prompt-bound chats break existing Library semantics | L | M | separate tables; prompts table untouched |
| R10 | Disk fill from uploads | L | M | default per-user quota (e.g. 250 MB) + cleanup of orphaned attachments |

---

## 9. Decisions (LOCKED — plan-only, nothing built yet)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Stream | Non-stream MVP first, streaming in week 2 |
| 2 | `.doc` / `.odt` | Dropped for v1 (users save as `.docx`/`.pdf`) |
| 3 | File limits | **25 MB/file**, 5 files/message, 250 MB/user quota (all env-configurable) |
| 4 | Images / scanned PDFs | Provider vision model (no local OCR) |
| 5 | Default landing view | **Chat** (Engineer stays in top bar) |
| 6 | Implementation | **NOT started** — this is the approved plan only; work begins on explicit go |

---

## 10. Phased roadmap (estimates = dev days)

| Phase | Deliverable | Est. |
|-------|-------------|------|
| **M0 Foundation** | DB schema + CRUD + auth scoping + tests | 2–3 d |
| **M1 Chat API** | `llm_client.chat()`, history windowing, regenerate, non-stream messages endpoint | 3–4 d |
| **M2 Chat UI** | sidebar + projects UI, bubble layout, markdown rendering, copy/actions, streaming SSE + DOM | 4–5 d |
| **M3 File parsing** | upload endpoint, parser registry (csv/xlsx/docx/pdf/text), images→vision, quota+isolation | 4–5 d |
| **M4 Prompt→Chat glue** | Send-to-Chat buttons (Engineer/Library/Orchestrator) + batch chat creation | 1–2 d |
| **M5 Hardening** | full test pass, PyInstaller + installer build, DEPLOYMENT.md updates, security review | 2–3 d |
| **Total** | | **≈ 16–22 dev days** |

**Kept intact throughout:** auth, per-user isolation pattern, engine tabs, export/
diff/orchestrator, native window, PWA, installer. All additions are additive —
no existing behavior removed; existing 22 tests keep passing, new suites added.

---

## 11. Testing strategy

- `tests/test_chat.py` — messages round-trip, history building, system-prompt
  binding, regenerate, isolation (user A can't read B's chats/files).
- `tests/test_files.py` — each parser against a tiny fixture file
  (generate .xlsx/.docx/.pdf in fixtures), bad-file isolation, size caps,
  unsupported-type rejection, path traversal attempt → 400.
- `tests/test_api.py` — new endpoints behind auth middleware, streaming SSE shape.
- Manual: native window + browser + mobile-PWA + cross-provider (Gemini, OpenAI,
  Groq, OpenRouter, local Ollama).