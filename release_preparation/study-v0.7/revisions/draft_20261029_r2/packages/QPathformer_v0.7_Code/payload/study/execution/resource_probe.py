"""Read-only effective numerical-runtime inspection; no library setters."""
import ctypes
import hashlib
from pathlib import Path
import platform
import sys
import time


def process_resources():
    """Peak resident set from the kernel and whole-process consumed CPU time."""
    result = {"process_cpu_seconds": time.process_time(), "pid": __import__("os").getpid(),
              "scope": "Whole fit child including imports, verification and watchdog through sampling time"}
    if sys.platform == "win32":
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        result.update({"peak_working_set_bytes": int(counters.PeakWorkingSetSize),
                       "working_set_bytes_at_sample": int(counters.WorkingSetSize),
                       "private_usage_bytes_at_sample": int(counters.PrivateUsage),
                       "memory_source": "Win32_GetProcessMemoryInfo"})
    else:
        import resource
        result["peak_working_set_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        result["memory_source"] = "getrusage_linux_kib"
    return result


def inspect():
    import numpy as np
    candidates = list((Path(np.__file__).resolve().parent.parent/"numpy.libs").glob("*openblas*.dll"))
    if len(candidates) != 1:
        raise RuntimeError("Expected one packaged OpenBLAS DLL for official Windows runtime")
    dll = candidates[0]
    library = ctypes.CDLL(str(dll))
    threads = getattr(library, "scipy_openblas_get_num_threads64_")
    threads.restype = ctypes.c_int
    config = getattr(library, "scipy_openblas_get_config64_")
    config.restype = ctypes.c_char_p
    return {"python": platform.python_version(), "interpreter": str(Path(sys.executable).resolve()),
            "numpy_version": np.__version__, "numpy_file": str(Path(np.__file__).resolve()),
            "openblas_dll": str(dll), "openblas_dll_sha256": hashlib.sha256(dll.read_bytes()).hexdigest(),
            "openblas_config": config().decode("ascii"), "effective_blas_threads": int(threads()),
            "gpu_used": False}


if __name__ == "__main__":
    import json
    print(json.dumps(inspect(), indent=2))
