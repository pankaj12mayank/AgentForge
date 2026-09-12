"""Lightweight, dependency-free system health reporting for AgentForge.

Used by ``/api/health`` so the UI can show how the app, database, disk,
memory, and CPU are doing without relying on psutil or any external agent.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
import time
from ctypes import wintypes

from prompt_generation.config import WRITABLE_DIR
from prompt_generation.db import DB_PATH, get_db_health

_STARTED_AT = time.time()
_WIN = sys.platform == "win32"

# CPU sampling is moderately expensive (it needs two snapshots), so cache it.
_cpu_cache: dict = {"at": 0.0, "value": None}


def _memory_info() -> dict:
    if not _WIN:
        return {}
    try:

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return {
                "load": int(stat.dwMemoryLoad),
                "used_gb": round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024**3), 1),
                "total_gb": round(stat.ullTotalPhys / (1024**3), 1),
            }
    except Exception:
        pass
    return {}


def _sample_windows_cpu() -> tuple:
    class FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    def _times() -> tuple:
        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        )

        def to_us(ft: FILETIME) -> float:
            return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 10.0

        return to_us(idle), to_us(kernel), to_us(user)

    idle0, kernel0, user0 = _times()
    time.sleep(0.3)
    idle1, kernel1, user1 = _times()
    idle = idle1 - idle0
    busy = (kernel1 - kernel0) + (user1 - user0) - idle
    total = busy + idle
    return round(100.0 * busy / total, 1) if total > 0 else 0.0


def _cpu_percent() -> float | None:
    if not _WIN:
        return None
    now = time.time()
    if _cpu_cache["at"] and (now - _cpu_cache["at"]) < 3:
        return _cpu_cache["value"]
    try:
        value = _sample_windows_cpu()
    except Exception:
        value = None
    _cpu_cache.update(at=now, value=value)
    return value


def uptime_seconds() -> int:
    return int(time.time() - _STARTED_AT)


def get_system_health() -> dict:
    disk = {}
    try:
        usage = shutil.disk_usage(WRITABLE_DIR)
        disk = {
            "free_gb": round(usage.free / (1024**3), 1),
            "total_gb": round(usage.total / (1024**3), 1),
        }
    except OSError:
        pass

    db = {"path": str(DB_PATH)}
    try:
        health = get_db_health()
        db.update(health)
    except Exception as exc:  # pragma: no cover - defensive
        db.update({"ok": False, "error": str(exc)})

    return {
        "server": "online",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(_STARTED_AT)),
        "uptime_seconds": uptime_seconds(),
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu_cores": os.cpu_count() or 0,
        "cpu_percent": _cpu_percent(),
        "memory": _memory_info(),
        "disk": disk,
        "db": db,
        "writable_dir": str(WRITABLE_DIR),
    }