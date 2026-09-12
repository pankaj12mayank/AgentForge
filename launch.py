"""AgentForge launcher.

Run:
    python launch.py               # start the app in its own native window
    python launch.py --browser     # open the system web browser instead
    python launch.py --app         # force the native app window (default)
    python launch.py --no-browser  # silent server, no window at all

Reads PORT from .env as the first port to try. If it is already in use (other
projects), the next free port is used automatically. Set PROMPT_GEN_NO_BROWSER=1
to skip opening a window.

The native app window is backed by pywebview (WebView2 on Windows) and shows the
exact same UI as the browser; if the WebView runtime is unavailable it falls back
to opening the system browser.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from prompt_generation.config import WRITABLE_DIR  # noqa: F401

_REPO_ROOT = Path(__file__).resolve().parent


def _bind_listener(host: str, start: int, attempts: int = 64) -> socket.socket:
    """Open + bind the first free TCP port, returning the held listener socket.

    Holding the socket open removes the check-then-bind race: the port stays
    reserved until uvicorn takes it over, so concurrent double-launches cannot
    crash on the same port.
    """
    last_err: OSError | None = None
    for port in range(start, start + attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Windows: EXCLUSIVEADDRUSE makes the port truly owned while we hold it,
        # so a concurrent second instance cannot silently steal the same port.
        # Elsewhere SO_REUSEADDR keeps the usual bind semantics.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            sock.close()
            last_err = exc
            continue
        return sock
    raise SystemExit(
        f"No free TCP port in range {start}..{start + attempts - 1}.\n"
        f"Tried to bind to '{host}'.\n"
        "Close other apps using those ports or set a higher PORT in .env.\n"
    ) from last_err


def _maybe_open_browser(url: str) -> None:
    if os.getenv("PROMPT_GEN_NO_BROWSER", "").strip() in ("1", "true", "yes"):
        return

    def _open() -> None:
        time.sleep(1.5)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


def _open_native_window(url: str) -> bool:
    """Open AgentForge in its own native window. Returns True if a window was
    actually created and shown (blocking until it is closed by the user)."""
    try:
        import webview
    except Exception:
        return False

    try:
        webview.create_window(
            "AgentForge",
            url,
            width=1400,
            height=900,
            min_size=(1000, 620),
            background_color="#060811",
            text_select=True,
        )
        webview.start()
    except Exception:
        return False
    return True


def _parse_args(argv: list[str]) -> dict:
    args = {"no_browser": False, "browser": False, "app": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--no-browser":
            args["no_browser"] = True
        elif a == "--browser":
            args["browser"] = True
        elif a == "--app":
            args["app"] = True
        elif a in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        i += 1
    return args


def _silence_console_output() -> None:
    """In --noconsole (windowed) builds sys.stdout/stderr are None. Redirect them
    to a log file so the app runs as a proper background/native app and no
    terminal window is needed; every launch that still has a console keeps it."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_path = (Path(os.environ.get("WRITABLE_DIR", str(Path(WRITABLE_DIR)))) / "app.log").resolve()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log_path, "a", encoding="utf-8")
        if sys.stdout is None:
            sys.stdout = fh
        if sys.stderr is None:
            sys.stderr = fh
    except Exception:
        pass


def main(argv: list[str] | None = None) -> None:
    argv = list(argv) if argv is not None else sys.argv[1:]
    args = _parse_args(argv)
    _silence_console_output()
    load_dotenv(_REPO_ROOT / ".env")

    preferred = int(os.getenv("PORT", "8765"))
    bind_host = os.getenv("HOST", "127.0.0.1")
    sock = _bind_listener(bind_host, preferred)
    listen_port = sock.getsockname()[1]
    os.environ["LISTEN_PORT"] = str(listen_port)

    url = f"http://127.0.0.1:{listen_port}/"
    if listen_port != preferred:
        print(
            f"PORT {preferred} from .env is busy (another app may be using it).\n"
            f"Listening on {listen_port} instead. Open: {url}\n"
            f"(Change PORT in .env only when you want a different *preferred* port.)\n"
        )
    else:
        print(f"AgentForge -> {url}  (PORT from .env)\n")

    if bind_host != "127.0.0.1":
        print(f"WARNING: Binding to host {bind_host} exposes this app to the network.")

    server = uvicorn.Server(
        uvicorn.Config(
            "pg_ui.app:app",
            host=bind_host,
            port=listen_port,
            reload=False,
        )
    )

    if args["no_browser"]:
        server.run(sockets=[sock])
        return

    # Native window first (default). The uvicorn server runs in the background
    # thread because pywebview needs the GUI pump on the main thread.
    if not args["browser"] and _native_window_available():
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        deadline = time.time() + 10
        while not server.started and thread.is_alive() and time.time() < deadline:
            time.sleep(0.05)
        if _open_native_window(url):
            # The user closed the app window -> shut the server down and exit.
            server.should_exit = True
            thread.join(timeout=5)
            return
        # Native window unavailable at runtime -> fall back to the browser but
        # keep serving (same as the --browser path below).
        _maybe_open_browser(url)
        thread.join()
        return

    if not args["no_browser"]:
        _maybe_open_browser(url)

    server.run(sockets=[sock])


def _native_window_available() -> bool:
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()