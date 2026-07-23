"""Best-effort, cross-platform peak-memory measurement using only the
standard library (plus ``ctypes`` on Windows). Returns None if it cannot be
measured on the current platform -- callers must treat that as a documented
limitation, not an error.
"""

from __future__ import annotations

import sys
from typing import Optional


def get_peak_memory_mb() -> Optional[float]:
    if sys.platform.startswith("win"):
        return _get_peak_memory_mb_windows()
    return _get_peak_memory_mb_unix()


def _get_peak_memory_mb_unix() -> Optional[float]:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        # On Linux ru_maxrss is in KB; on macOS it is in bytes.
        if sys.platform == "darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except (ImportError, AttributeError, OSError):
        return None


def _get_peak_memory_mb_windows() -> Optional[float]:
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        success = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        if not success:
            return None
        return counters.PeakWorkingSetSize / (1024 * 1024)
    except (ImportError, AttributeError, OSError, ValueError):
        return None
