"""OS process identity; PID alone is never sufficient for recovery or termination."""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import signal


def identity(pid=None):
    pid = os.getpid() if pid is None else int(pid)
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error in (87, 1168):
                return None
            raise OSError(error, "Process identity cannot be established; fail closed", pid)
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(x) for x in times)):
                raise ctypes.WinError(ctypes.get_last_error())
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ctypes.WinError(ctypes.get_last_error())
            if code.value != 259:
                return None
            return {"pid": pid, "creation_token": str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime),
                    "identity_source": "Win32_GetProcessTimes"}
        finally:
            kernel.CloseHandle(handle)
    path = Path(f"/proc/{pid}/stat")
    try:
        fields = path.read_text().split(") ", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": pid, "creation_token": fields[19], "identity_source": "proc_starttime"}
    except FileNotFoundError:
        return None


def alive(expected):
    return expected is not None and identity(expected["pid"]) == expected


def terminate(expected):
    """Terminate only a process whose kernel creation identity still matches."""
    if not alive(expected):
        return False
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x0001 | 0x1000, False, expected["pid"])
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not alive(expected):
                return False
            if not kernel.TerminateProcess(handle, 125):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
    else:
        os.kill(expected["pid"], signal.SIGTERM)
    return True
