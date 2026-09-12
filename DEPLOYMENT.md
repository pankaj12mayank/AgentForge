# AgentForge — Deployment Guide (Free → Paid)

This guide takes AgentForge from **free hosting** all the way to a **real production
server**. AgentForge is a single FastAPI app with a SQLite database — no external
database needed, which keeps it cheap and simple to host.

> Prices/free tiers change often. Every number below is a 2026 estimate —
> check the provider's site before committing.

---

## 1. What you are deploying

* One Python app (`launch.py` → `pg_ui.app`) that binds `HOST:PORT`.
* One SQLite file that must **persist**: `data/config.sqlite` (users + prompts +
  settings) and `data/.secret_key` (encryption key).
* Auth is **ON by default** — users register + sign in (or one shared password).
* No external DB, no background workers, **single instance** (the rate limiter is
  in-memory, so don't scale to multiple workers behind one URL).

Include a `Dockerfile` (already in the repo) for all container platforms.

| Path | Cost | Good for |
|------|------|----------|
| Render free | ₹0 / $0 | Demos, testing (sleeps after ~15 min idle) |
| Oracle Cloud "Always Free" VM | ₹0 / $0 | A real free 24/7 server |
| Railway | $5 trial → ~$5/mo | Fast git-push deploys |
| Cheap VPS (DigitalOcean / Hostinger) | ~$4–6/mo | Recommended production |
| Any VPS + Caddy | VPS cost | Simplest full control + HTTPS |

---

## 2. Production environment variables

Set these on the host / PaaS dashboard / Docker.

```env
HOST=0.0.0.0                 # required on a server (bind all interfaces)
PORT=8765                    # Render/Railway expects a PORT env var
PROMPT_GEN_NO_BROWSER=1      # headless server (no native window on a VPS)

# Auth — keep ON. Pick one style:
APP_AUTH_USERS=1             # multi-user register + login (default anyway)
# APP_AUTH_TOKEN=<secret>    # OR one shared password mode

# Only if your LLM is a local/LAN server (Ollama, LM Studio, vLLM):
# AGENTFORGE_ALLOW_LOCAL_LLM=1

# Optional: put the DB somewhere specific
# PROMPT_GEN_DB_PATH=/data/config.sqlite
```

---

## 3. Path A — Free: Render (Web Service, easy)

1. Push the repo to GitHub.
2. Render → **New → Web Service** → pick the repo.
3. Runtime: **Docker** (uses the repo's `Dockerfile`).
4. Env vars: set the block above (`HOST=0.0.0.0`, `PORT` auto, `PROMPT_GEN_NO_BROWSER=1`).
5. **Free tier**: 512 MB / 0.1 CPU, auto HTTPS, **but** spins down after ~15 min
   idle and cold-starts in 30–60 s. Fine for a demo, not for 24/7 use.
6. **Data caveat**: Render free disk is **ephemeral** — `config.sqlite` resets on
   redeploy. For persistence on Render you need a **Persistent Disk** (paid tier)
   mounted at `/app/data`.
7. Upgrade later: Starter ~$7/mo + a small disk → always online + data persists.

## 4. Path B — Free: Oracle Cloud "Always Free" VM (real 24/7 server)

The only true "free 24/7" option. Pick the **Always Free** ARM shape (4 OCPU /
24 GB RAM) or an AMD one.

```bash
# after you create the Ubuntu VM and SSH in:
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable --now docker

git clone <your-repo> agentforge && cd agentforge

# build + run with a persistent volume
sudo docker build -t agentforge .
sudo docker run -d --name af \
  --restart unless-stopped \
  -p 80:8765 \
  -v /opt/agentforge-data:/app/data \
  -e HOST=0.0.0.0 -e PORT=8765 \
  -e PROMPT_GEN_NO_BROWSER=1 \
  -e APP_AUTH_USERS=1 \
  agentforge
```

Then add HTTPS with Caddy (free auto-cert):

```bash
sudo apt install -y caddy
# /etc/caddy/Caddyfile:
# yourdomain.com {
#     reverse_proxy 127.0.0.1:8765
# }
sudo systemctl restart caddy
```

Your data lives in `/opt/agentforge-data` — safe across restarts/redeploys.

## 5. Path C — Paid: cheap VPS (~$4–6/mo)

Same container flow as Path B, on DigitalOcean (Droplet $6), Hostinger (KS/KVM),
LightNode, etc. Use Caddy or nginx+certbot for HTTPS. This is the recommended
**production** setup: 24/7 uptime, your own domain, full control.

## 6. Persistent data & backups (MUST)

SQLite must survive restarts and disasters:

* **Docker / VPS**: mount a volume (`-v /opt/agentforge-data:/app/data`) — never
  run without a volume.
* **Backup** (nightly cron on the VPS):

```bash
# /etc/cron.d/agentforge-backup
0 3 * * * root sqlite3 /opt/agentforge-data/config.sqlite ".backup /opt/backups/af-$(date +\%F).sqlite" && find /opt/backups -name 'af-*.sqlite' -mtime +14 -delete
```

* Restore = copy the `.sqlite` back into the data dir (while app stopped), done.
* On PaaS without a volume, add a scheduled task that downloads the SQLite file
  (or use their managed object storage).

---

## 7. HTTPS & security checklist

| Item | Status | Action |
|------|--------|--------|
| Auth ON | ✅ default | keep `APP_AUTH_USERS=1` (or `APP_AUTH_TOKEN`) |
| HTTPS | ⚠️ do it | Caddy / nginx+certbot / PaaS managed TLS |
| Session cookie | HttpOnly + SameSite=Lax | over HTTPS it travels encrypted; `Secure` flag is optional hardening (set via a reverse proxy if you want it strict) |
| API keys | ✅ Fernet-encrypted at rest | machine-local key in `.secret_key` — back it up with the DB |
| SSRF guard | ✅ default | outbound LLM calls blocked to private/LAN unless `AGENTFORGE_ALLOW_LOCAL_LLM=1` |
| Single instance | ⚠️ important | rate limiter is in-memory — run **one** container, never 2+ behind a load balancer |
| Desktop installs | ✅ | loopback-only by default (`HOST=127.0.0.1`) — don't bind `0.0.0.0` on your own PC |

> Don't run the Windows EXE / installer on the server. The git/Docker deployment
> is the server path; the EXE is for desktop users.

---

## 8. Mobile / PWA note

Mobile "Install app" (Add to Home Screen) for the PWA needs **HTTPS** — your
Caddy/nginx/PaaS TLS covers it. The PWA works on the same URL users open in the
browser.

---

## 9. Recommended upgrade ladder (if you grow)

1. **Free demo** (Render free) → 2. **Free 24/7** (Oracle Always-Free VM + Caddy)
   → 3. **Cheap VPS** ($4–6/mo, same flow) → 4. **Bigger VPS** if you add AI-heavy
   features. No architecture change ever required — every step is the same app +
   same Dockerfile.