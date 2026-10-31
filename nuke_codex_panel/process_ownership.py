"""Which MCP sidecar processes the panel owns, and how to end exactly those (Linux, macOS, Windows).

Qt free and standard library only: the stdio MCP sidecar imports this too.

Ownership is a per-user private *registry*, not a scan of the machine. A sidecar the panel launched
(it inherits ``NUKE_CODEX_CONTROL_ID`` / ``NUKE_CODEX_CONTROL_EPOCH``) registers itself at startup,
before it serves any tool call, with its control id, epoch, PID, the operating system's own birth
identity of the process and its executable, and unregisters when it exits. A sidecar without a
control id (an external MCP client's) never registers, so it is never touched.

The panel (``lease_processes`` / ``process_alive`` / ``signal_processes``) trusts a registration
only while the live process still has the *same birth identity and executable* as when it
registered; a PID that was reused by an unrelated process, or an executable that was replaced, is
never the owned process. The identity is read again immediately before every signal:

* Linux:   ``/proc/<pid>/stat`` start time (+ ``boot_id``) and ``/proc/<pid>/exe``; the signal goes
           through a ``pidfd`` opened *before* the check, so the PID cannot be recycled in between
           (a verified ``kill`` only where ``pidfd`` is unavailable).
* macOS:   ``proc_pidinfo(PROC_PIDTBSDINFO)`` start time and ``proc_pidpath`` (libproc via ctypes);
           verified ``kill`` right after the check.
* Windows: ``GetProcessTimes`` creation time and ``QueryFullProcessImageNameW`` read from the very
           handle that is then given to ``TerminateProcess``. Windows has no graceful signal for a
           console-less process, so TERM and KILL both terminate. ``os.kill`` is never used on
           Windows (it terminates the process even for signal 0).

Whatever cannot be verified is an error (``ProcessIdentityUnavailable``), never "no processes": the
caller must not renew an agent whose old tool server it could not confirm gone.
"""

from __future__ import annotations

import atexit
import dataclasses
import errno
import hashlib
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

from . import runtime_paths
from .runtime_paths import RuntimePathError, RuntimePathMissing, UnsafeRuntimePath

# Environment variables that carry the harness's control identity to its MCP sidecar: the id is
# stable for the client, the epoch counts agent process launches (a per-process lease).
CONTROL_ID_ENV = "NUKE_CODEX_CONTROL_ID"
CONTROL_EPOCH_ENV = "NUKE_CODEX_CONTROL_EPOCH"
CONTROL_ID_LIMIT = 64

# The MCP sidecar is started as ``python -m nuke_codex_panel.mcp_server.server``.
SIDECAR_MARKER = "nuke_codex_panel.mcp_server"
REGISTRY_DIRECTORY = "sidecars"
SCHEMA = 1

# The only two requests: ask to end (SIGTERM; TerminateProcess on Windows) and end now (SIGKILL;
# TerminateProcess on Windows). Plain integers: ``signal.SIGKILL`` does not exist on Windows.
TERM = 15
KILL = 9

_STALE_TEMPORARY_SECONDS = 300

_LINUX = sys.platform.startswith("linux")
_DARWIN = sys.platform == "darwin"
_WINDOWS = sys.platform == "win32"


class ProcessOwnershipError(RuntimeError):
    """Ownership could not be established, read or enforced."""


class ProcessIdentityUnavailable(ProcessOwnershipError):
    """The operating system did not let us verify a process; nothing may be assumed about it."""


@dataclasses.dataclass(frozen=True)
class ProcessIdentity:
    """What the operating system says a running process is: stable for its whole life, unique per PID reuse."""

    pid: int
    birth: str
    exe: str | None


def normalize_control_id(value) -> str:
    """The control id exactly as the bridge and the sidecar normalise it."""
    return str(value or "").strip()[:CONTROL_ID_LIMIT]


def _valid_pid(pid) -> bool:
    return isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid < 2**31


# ---------------------------------------------------------------------------
# Operating-system identity
# ---------------------------------------------------------------------------


def identify_process(pid: int) -> ProcessIdentity | None:
    """Birth identity and executable of the running process ``pid``.

    ``None`` when no such process runs (an exited or zombie process is not running). Raises
    ``ProcessIdentityUnavailable`` when the process exists but the operating system does not let
    this user read its identity, or the platform has no implementation.
    """
    if not _valid_pid(pid):
        return None
    if _LINUX:
        return _linux_identify(pid)
    if _DARWIN:
        return _darwin_identify(pid)
    if _WINDOWS:
        return _windows_identify(pid)
    raise ProcessIdentityUnavailable("process identity is not implemented for platform %r" % sys.platform)


def pid_running(pid: int) -> bool:
    """Whether ``pid`` is a running process (not exited, not a zombie).

    Pure observation for discovery records: it never signals, needs no registration and never
    terminates anything (``os.kill(pid, 0)`` would terminate the process on Windows). Raises
    ``ProcessIdentityUnavailable`` only if the operating system refuses to answer at all.
    """
    if not _valid_pid(pid):
        return False
    if _WINDOWS:
        return _windows_running(pid)
    if _LINUX:
        return _linux_running(pid)
    if _DARWIN:
        return _darwin_running(pid)
    return _posix_signal_zero(pid)


def _posix_signal_zero(pid: int) -> bool:
    try:
        os.kill(pid, 0)  # POSIX only: signal 0 delivers nothing
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# -- Linux ------------------------------------------------------------------

_BOOT_ID: str | None = None
_LINUX_DEAD_STATES = ("Z", "X", "x")


def _boot_id() -> str:
    global _BOOT_ID
    if _BOOT_ID is None:
        try:
            with open("/proc/sys/kernel/random/boot_id", "r", encoding="ascii") as handle:
                _BOOT_ID = handle.read().strip()
        except OSError:
            _BOOT_ID = ""
    return _BOOT_ID


def _linux_stat(pid: int):
    """``(state, start_ticks)`` from /proc/<pid>/stat, or None if the process does not exist."""
    try:
        with open("/proc/%d/stat" % pid, "rb") as handle:
            data = handle.read()
    except (FileNotFoundError, ProcessLookupError):
        if os.path.isdir("/proc/self"):
            return None
        raise ProcessIdentityUnavailable("/proc is not available; cannot verify processes")
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return None
        raise ProcessIdentityUnavailable("cannot read /proc/%d/stat: %s" % (pid, exc)) from exc
    # "pid (comm) S ..." where comm may contain spaces or parentheses: the fields follow the last ")".
    fields = data.rsplit(b")", 1)[-1].split()
    if len(fields) < 20:
        raise ProcessIdentityUnavailable("unexpected /proc/%d/stat format" % pid)
    return fields[0].decode("ascii", "replace"), fields[19].decode("ascii", "replace")


def _linux_identify(pid: int) -> ProcessIdentity | None:
    state = _linux_stat(pid)
    if state is None or state[0] in _LINUX_DEAD_STATES:
        return None
    try:
        exe = os.readlink("/proc/%d/exe" % pid)
    except OSError:
        if _linux_stat(pid) is None:  # exited while we looked
            return None
        exe = None  # exists but not readable by us (foreign user): the caller decides
    boot = _boot_id()
    return ProcessIdentity(pid, "%s:%s" % (boot, state[1]) if boot else state[1], exe)


def _linux_running(pid: int) -> bool:
    try:
        state = _linux_stat(pid)
    except ProcessIdentityUnavailable:
        return _posix_signal_zero(pid)  # no usable /proc: signal 0 is safe on POSIX
    return state is not None and state[0] not in _LINUX_DEAD_STATES


# -- macOS ------------------------------------------------------------------

_LIBPROC = None
_PROC_PIDTBSDINFO = 3  # <sys/proc_info.h>
_PROC_PIDPATHINFO_MAXSIZE = 4 * 1024  # 4 * MAXPATHLEN
_DARWIN_SZOMB = 5  # <sys/proc.h>: awaiting collection by the parent
_PROC_BSDINFO_SIZE = 136  # sizeof(struct proc_bsdinfo)


def _libproc():
    """libproc with ``proc_pidinfo`` / ``proc_pidpath`` and the ``struct proc_bsdinfo`` layout (xnu proc_info.h)."""
    global _LIBPROC
    if _LIBPROC is not None:
        return _LIBPROC
    import ctypes
    import ctypes.util
    from types import SimpleNamespace

    class ProcBsdInfo(ctypes.Structure):
        _fields_ = [
            ("pbi_flags", ctypes.c_uint32),
            ("pbi_status", ctypes.c_uint32),
            ("pbi_xstatus", ctypes.c_uint32),
            ("pbi_pid", ctypes.c_uint32),
            ("pbi_ppid", ctypes.c_uint32),
            ("pbi_uid", ctypes.c_uint32),
            ("pbi_gid", ctypes.c_uint32),
            ("pbi_ruid", ctypes.c_uint32),
            ("pbi_rgid", ctypes.c_uint32),
            ("pbi_svuid", ctypes.c_uint32),
            ("pbi_svgid", ctypes.c_uint32),
            ("rfu_1", ctypes.c_uint32),
            ("pbi_comm", ctypes.c_char * 16),  # MAXCOMLEN
            ("pbi_name", ctypes.c_char * 32),  # 2 * MAXCOMLEN
            ("pbi_nfiles", ctypes.c_uint32),
            ("pbi_pgid", ctypes.c_uint32),
            ("pbi_pjobc", ctypes.c_uint32),
            ("e_tdev", ctypes.c_uint32),
            ("e_tpgid", ctypes.c_uint32),
            ("pbi_nice", ctypes.c_int32),
            ("pbi_start_tvsec", ctypes.c_uint64),
            ("pbi_start_tvusec", ctypes.c_uint64),
        ]

    if ctypes.sizeof(ProcBsdInfo) != _PROC_BSDINFO_SIZE:
        raise ProcessIdentityUnavailable(
            "struct proc_bsdinfo is %d bytes here, expected %d" % (ctypes.sizeof(ProcBsdInfo), _PROC_BSDINFO_SIZE)
        )
    try:
        library = ctypes.CDLL(ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib", use_errno=True)
        library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        library.proc_pidinfo.restype = ctypes.c_int
        library.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        library.proc_pidpath.restype = ctypes.c_int
    except (OSError, AttributeError) as exc:
        raise ProcessIdentityUnavailable("libproc is not available: %s" % exc) from exc
    _LIBPROC = SimpleNamespace(ctypes=ctypes, library=library, Info=ProcBsdInfo)
    return _LIBPROC


def _darwin_bsdinfo(pid: int):
    """``struct proc_bsdinfo`` of ``pid``, or None if no such process; raises if unreadable."""
    lib = _libproc()
    ctypes = lib.ctypes
    info = lib.Info()
    ctypes.set_errno(0)
    written = lib.library.proc_pidinfo(pid, _PROC_PIDTBSDINFO, 0, ctypes.byref(info), ctypes.sizeof(info))
    if written == ctypes.sizeof(info):
        return info
    error = ctypes.get_errno()
    if error == errno.ESRCH:
        return None
    raise ProcessIdentityUnavailable(
        "proc_pidinfo(%d) returned %d: %s" % (pid, written, os.strerror(error) if error else "no error code")
    )


def _darwin_identify(pid: int) -> ProcessIdentity | None:
    info = _darwin_bsdinfo(pid)
    if info is None or info.pbi_status == _DARWIN_SZOMB:
        return None
    lib = _libproc()
    ctypes = lib.ctypes
    buffer = ctypes.create_string_buffer(_PROC_PIDPATHINFO_MAXSIZE)
    ctypes.set_errno(0)
    length = lib.library.proc_pidpath(pid, buffer, _PROC_PIDPATHINFO_MAXSIZE)
    if length > 0:
        exe = os.fsdecode(buffer.value)
    elif ctypes.get_errno() == errno.ESRCH:
        return None
    else:
        exe = None
    return ProcessIdentity(pid, "%d.%06d" % (info.pbi_start_tvsec, info.pbi_start_tvusec), exe)


def _darwin_running(pid: int) -> bool:
    try:
        info = _darwin_bsdinfo(pid)
    except ProcessIdentityUnavailable:
        return _posix_signal_zero(pid)
    return info is not None and info.pbi_status != _DARWIN_SZOMB


# -- Windows ----------------------------------------------------------------

_WINAPI = None
_PROCESS_TERMINATE = 0x0001
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_STILL_ACTIVE = 259
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 0x102
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87


def _winapi():
    """kernel32 process calls, declared once with explicit prototypes (handles are 64-bit on x64)."""
    global _WINAPI
    if _WINAPI is not None:
        return _WINAPI
    import ctypes
    from ctypes import wintypes
    from types import SimpleNamespace

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    _WINAPI = SimpleNamespace(ctypes=ctypes, wintypes=wintypes, kernel32=kernel32)
    return _WINAPI


def _win_error(code: int) -> str:
    return str(_winapi().ctypes.WinError(code))


def _win_open(pid: int, access: int):
    """``(handle, 0)`` or ``(None, GetLastError())``."""
    w = _winapi()
    handle = w.kernel32.OpenProcess(access, False, pid)
    if handle:
        return handle, 0
    return None, w.ctypes.get_last_error()


def _win_open_for_query(pid: int):
    """``(handle, 0)`` with query access (plus SYNCHRONIZE when granted), else ``(None, GetLastError())``."""
    handle, error = _win_open(pid, _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE)
    if handle is None and error == _ERROR_ACCESS_DENIED:
        handle, error = _win_open(pid, _PROCESS_QUERY_LIMITED_INFORMATION)
    return handle, error


def _win_handle_running(handle) -> bool:
    w = _winapi()
    code = w.wintypes.DWORD()
    if not w.kernel32.GetExitCodeProcess(handle, w.ctypes.byref(code)):
        raise ProcessIdentityUnavailable("GetExitCodeProcess failed: %s" % _win_error(w.ctypes.get_last_error()))
    if code.value != _STILL_ACTIVE:
        return False
    # 259 is also a legal exit code: a signalled process object is the definitive answer. Without
    # SYNCHRONIZE access the wait fails and the exit code alone stands.
    return w.kernel32.WaitForSingleObject(handle, 0) != _WAIT_OBJECT_0


def _win_identity(pid: int, handle) -> ProcessIdentity | None:
    """Identity read from an open handle; None if the process has exited."""
    w = _winapi()
    ctypes, wintypes = w.ctypes, w.wintypes
    if not _win_handle_running(handle):
        return None
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not w.kernel32.GetProcessTimes(
        handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)
    ):
        raise ProcessIdentityUnavailable("GetProcessTimes(%d) failed: %s" % (pid, _win_error(ctypes.get_last_error())))
    birth = (created.dwHighDateTime << 32) | created.dwLowDateTime
    capacity = 32768
    buffer = ctypes.create_unicode_buffer(capacity)
    size = wintypes.DWORD(capacity)
    exe = buffer.value if w.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)) else None
    return ProcessIdentity(pid, str(birth), exe)


def _windows_identify(pid: int) -> ProcessIdentity | None:
    w = _winapi()
    handle, error = _win_open_for_query(pid)
    if handle is None:
        if error == _ERROR_INVALID_PARAMETER:
            return None
        raise ProcessIdentityUnavailable("cannot open process %d: %s" % (pid, _win_error(error)))
    try:
        return _win_identity(pid, handle)
    finally:
        w.kernel32.CloseHandle(handle)


def _windows_running(pid: int) -> bool:
    w = _winapi()
    handle, error = _win_open_for_query(pid)
    if handle is None:
        if error == _ERROR_INVALID_PARAMETER:
            return False
        if error == _ERROR_ACCESS_DENIED:
            return True  # it exists; another user's or a protected process
        raise ProcessIdentityUnavailable("cannot open process %d: %s" % (pid, _win_error(error)))
    try:
        return _win_handle_running(handle)
    finally:
        w.kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Registry records
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _Record:
    path: Path
    control_id: str
    epoch: int | None
    pid: int
    birth: str
    exe: str


def _normalise_exe(path: str) -> str:
    if path.endswith(" (deleted)"):  # Linux: the file was replaced while the process kept running
        path = path[: -len(" (deleted)")]
    return os.path.normcase(path)


def _same_process(record: _Record, live: ProcessIdentity | None) -> bool:
    """Whether ``live`` is the process that registered ``record`` (False: it is gone or someone else's)."""
    if live is None or live.birth != record.birth:
        return False
    if live.exe is None:
        raise ProcessIdentityUnavailable(
            "cannot read the executable of process %d; its identity cannot be verified" % record.pid
        )
    return _normalise_exe(live.exe) == _normalise_exe(record.exe)


def _discard(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _registry(create: bool) -> Path | None:
    try:
        return runtime_paths.private_runtime_directory(REGISTRY_DIRECTORY, create=create)
    except RuntimePathMissing:
        if create:
            raise ProcessOwnershipError("the sidecar registry could not be created")
        return None
    except RuntimePathError as exc:
        raise ProcessOwnershipError("the sidecar registry is not usable: %s" % exc) from exc
    except OSError as exc:
        raise ProcessOwnershipError("the sidecar registry is not usable: %s" % exc) from exc


def _parse(path: Path, raw: bytes) -> _Record | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("marker") != SIDECAR_MARKER:
        return None
    pid, epoch = data.get("pid"), data.get("epoch")
    control_id, birth, exe = data.get("control_id"), data.get("birth"), data.get("exe")
    if (
        not _valid_pid(pid)
        or not isinstance(control_id, str)
        or not isinstance(birth, str) or not birth
        or not isinstance(exe, str) or not exe
        or not (epoch is None or (isinstance(epoch, int) and not isinstance(epoch, bool)))
    ):
        return None
    return _Record(path, control_id, epoch, pid, birth, exe)


def _registered() -> list[_Record]:
    """Every readable registration (not yet verified against the live processes)."""
    directory = _registry(create=False)
    if directory is None:
        return []
    try:
        with os.scandir(directory) as iterator:
            entries = [entry for entry in iterator if entry.name.endswith(".json")]
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise ProcessOwnershipError("cannot list the sidecar registry %s: %s" % (directory, exc)) from exc
    records = []
    for entry in entries:
        path = Path(entry.path)
        try:
            raw = runtime_paths.read_private_file(path)
        except FileNotFoundError:
            continue
        except UnsafeRuntimePath:
            continue  # never trusted, never acted on
        except OSError as exc:
            raise ProcessOwnershipError("cannot read the sidecar registration %s: %s" % (path, exc)) from exc
        record = _parse(path, raw)
        if record is None:
            _discard(path)
        else:
            records.append(record)
    return records


def _verify(record: _Record) -> bool:
    """True while the registered process still runs; a registration of a gone process is removed."""
    if _same_process(record, identify_process(record.pid)):
        return True
    _discard(record.path)
    return False


# ---------------------------------------------------------------------------
# The panel's view: find, check and end owned sidecars
# ---------------------------------------------------------------------------


def lease_processes(control_id: str, epoch: int) -> list[int]:
    """PIDs of the running Nuke MCP sidecars registered under this control id and process epoch.

    A registration counts only while the live process has the identity it registered with.
    Raises ``ProcessOwnershipError`` when the registry or a process cannot be verified: the answer
    is then unknown, not empty.
    """
    wanted = normalize_control_id(control_id)
    own = os.getpid()
    found = set()
    for record in _registered():
        if record.control_id != wanted or record.epoch != epoch or record.pid == own:
            continue
        if _verify(record):
            found.add(record.pid)
    return sorted(found)


def process_alive(pid: int) -> bool:
    """Whether the registered sidecar with this PID still runs.

    False when it exited (a zombie, awaiting only its parent's reaping, has), when the PID now
    belongs to an unrelated process, and when ``pid`` was never a registered sidecar.
    """
    for record in _registered():
        if record.pid == pid and _verify(record):
            return True
    return False


def signal_processes(pids, sig: int = TERM) -> None:
    """Ask (``TERM``) or force (``KILL``) the registered sidecars in ``pids`` to end.

    Each process's identity is re-read against its registration immediately before it is signalled;
    a PID that is not a registered, still-identical sidecar is skipped, never signalled. Raises
    ``ProcessIdentityUnavailable`` (after handling the others) if a process could not be verified or
    signalled. On Windows both requests terminate the process.
    """
    number = int(sig)
    if number not in (TERM, KILL):
        raise ValueError("only TERM (%d) and KILL (%d) are supported, not %r" % (TERM, KILL, sig))
    wanted = {pid for pid in pids if _valid_pid(pid)}
    own = os.getpid()
    failures = []
    for record in _registered():
        if record.pid not in wanted or record.pid == own:
            continue
        try:
            _signal_verified(record, number)
        except ProcessOwnershipError as exc:
            failures.append(str(exc))
    if failures:
        raise ProcessIdentityUnavailable("; ".join(failures))


def _signal_verified(record: _Record, number: int) -> None:
    if _WINDOWS:
        _windows_terminate(record)
    else:
        _posix_signal(record, number)


def _posix_signal(record: _Record, number: int) -> None:
    descriptor = None
    if _LINUX and hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
        try:
            # Opened BEFORE the identity check: the descriptor pins the process that owned this PID
            # now, so a recycled PID can never receive the signal.
            descriptor = os.pidfd_open(record.pid)
        except ProcessLookupError:
            _discard(record.path)
            return
        except OSError:
            descriptor = None  # no pidfd here (old kernel, sandbox): verified kill below
    try:
        if not _same_process(record, identify_process(record.pid)):
            _discard(record.path)
            return
        try:
            if descriptor is not None:
                signal.pidfd_send_signal(descriptor, number)
            else:
                os.kill(record.pid, number)
        except ProcessLookupError:
            return  # exited between the check and the signal; the registration is pruned on next look
        except PermissionError as exc:
            raise ProcessIdentityUnavailable("not permitted to signal process %d: %s" % (record.pid, exc)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _windows_terminate(record: _Record) -> None:
    """Terminate through a handle whose identity was just verified (no PID race, handle always closed)."""
    w = _winapi()
    ctypes = w.ctypes
    access = _PROCESS_TERMINATE | _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE
    handle, error = _win_open(record.pid, access)
    if handle is None:
        if error == _ERROR_INVALID_PARAMETER:
            _discard(record.path)
            return
        raise ProcessIdentityUnavailable("cannot open process %d to end it: %s" % (record.pid, _win_error(error)))
    try:
        if not _same_process(record, _win_identity(record.pid, handle)):
            _discard(record.path)
            return
        if not w.kernel32.TerminateProcess(handle, 1):
            error = ctypes.get_last_error()
            # TerminateProcess reports access denied when the process already exited.
            if error == _ERROR_ACCESS_DENIED and not _win_handle_running(handle):
                return
            raise ProcessIdentityUnavailable("cannot terminate process %d: %s" % (record.pid, _win_error(error)))
    finally:
        w.kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# The sidecar's view: register this process
# ---------------------------------------------------------------------------

_registrations: list[Path] = []
_registration_lock = threading.Lock()
_exit_hook_installed = False


def register_current_process(control_id: str, epoch: int | None, bridge_descriptor: str | None = None) -> Path:
    """Register this process as the sidecar of ``control_id`` / ``epoch``; call before serving any request.

    ``bridge_descriptor`` is the pinned bridge record (``NUKE_CODEX_BRIDGE_FILE``), if any: a
    sidecar whose runtime directory differs from the one the Nuke bridge uses could never be found
    by the panel, so that is refused. Raises ``ProcessOwnershipError`` (the sidecar must then not
    start) if the OS identity cannot be read or the record cannot be written privately. Records of
    processes that no longer exist are pruned on the way.
    """
    control_id = normalize_control_id(control_id)
    if not control_id:
        raise ProcessOwnershipError("a panel-managed sidecar needs a control id")
    identity = identify_process(os.getpid())
    if identity is None or identity.exe is None:
        raise ProcessIdentityUnavailable("cannot read the operating-system identity of this process")
    try:
        directory = runtime_paths.private_runtime_directory(REGISTRY_DIRECTORY, create=True)
    except (RuntimePathError, OSError) as exc:
        raise ProcessOwnershipError("the sidecar registry is not usable: %s" % exc) from exc
    if bridge_descriptor:
        _require_same_runtime_directory(bridge_descriptor, directory)
    _prune(directory)
    record = {
        "schema": SCHEMA,
        "marker": SIDECAR_MARKER,
        "control_id": control_id,
        "epoch": epoch,
        "pid": identity.pid,
        "birth": identity.birth,
        "exe": identity.exe,
        "registered_ns": time.time_ns(),
    }
    name = "sidecar-%d-%s.json" % (identity.pid, hashlib.sha256(identity.birth.encode("utf-8")).hexdigest()[:12])
    path = directory / name
    try:
        runtime_paths.write_private_file(path, json.dumps(record).encode("utf-8"))
    except OSError as exc:
        raise ProcessOwnershipError("cannot write the sidecar registration %s: %s" % (path, exc)) from exc
    global _exit_hook_installed
    with _registration_lock:
        _registrations.append(path)
        if not _exit_hook_installed:
            atexit.register(unregister_current_process)
            _exit_hook_installed = True
    return path


def unregister_current_process() -> None:
    """Remove this process's registration (idempotent; a killed process leaves one that is pruned later)."""
    with _registration_lock:
        paths = list(_registrations)
        _registrations.clear()
    for path in paths:
        _discard(path)


def _require_same_runtime_directory(bridge_descriptor: str, registry: Path) -> None:
    pinned = Path(bridge_descriptor).parent
    try:
        if not pinned.exists():
            return  # an invalid pin is a bridge-discovery matter reported when a tool is called
        same = os.path.samefile(pinned, registry.parent)
    except OSError as exc:
        raise ProcessOwnershipError("cannot compare the bridge runtime directory %s: %s" % (pinned, exc)) from exc
    if not same:
        raise ProcessOwnershipError(
            "the Nuke bridge's runtime directory (%s) is not this sidecar's (%s); the panel could not find this "
            "process to retire it" % (pinned, registry.parent)
        )


def _prune(directory: Path) -> None:
    """Best effort: drop registrations of processes that are gone, and abandoned temporary files."""
    try:
        records = _registered()
    except ProcessOwnershipError:
        records = []
    for record in records:
        try:
            _verify(record)
        except ProcessOwnershipError:
            pass  # unverifiable: leave it; it is neither trusted nor deleted
    cutoff = time.time() - _STALE_TEMPORARY_SECONDS
    try:
        with os.scandir(directory) as iterator:
            stale = [e.path for e in iterator if e.name.endswith(".tmp") and e.stat(follow_symlinks=False).st_mtime < cutoff]
    except OSError:
        return
    for path in stale:
        _discard(Path(path))
