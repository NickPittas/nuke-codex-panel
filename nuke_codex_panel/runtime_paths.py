"""Per-user private runtime directories shared by the Nuke bridge, the MCP sidecar and process ownership.

Qt free and standard library only: the stdio MCP sidecar imports this too. The directory holds
bridge discovery records (they carry a bearer token) and the sidecar ownership registry, so it is
always the current user's, never a link and never readable or writable by anyone else:

* Linux:   ``$XDG_RUNTIME_DIR`` (else the temporary directory) ``/nuke-codex-panel-<uid>``, mode 0700.
* macOS:   the per-user secure temporary directory (``confstr(_CS_DARWIN_USER_TEMP_DIR)``, never
           the environment) ``/nuke-codex-panel-<uid>``, mode 0700.
* Windows: the Known Folder ``LocalAppData`` (never an environment variable that a child may have
           redirected) ``\\NukePi\\runtime`` with a protected DACL for the current user and SYSTEM.

``private_runtime_directory`` creates and validates; every call re-validates, so a directory that
was replaced by a link or loosened by someone else is refused rather than trusted.
"""

from __future__ import annotations

import os
import secrets
import stat
import struct
import sys
import tempfile
from pathlib import Path

DIRECTORY_PREFIX = "nuke-codex-panel-"
WINDOWS_APP_DIRECTORY = "NukePi"
WINDOWS_RUNTIME_DIRECTORY = "runtime"
MAX_FILE_BYTES = 64 * 1024

# <unistd.h>: _CS_DARWIN_USER_TEMP_DIR (Apple Libc). os.confstr accepts the raw integer.
_CS_DARWIN_USER_TEMP_DIR = 65537
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

_WINDOWS = sys.platform == "win32"
_DARWIN = sys.platform == "darwin"


class RuntimePathError(RuntimeError):
    """A runtime directory or file cannot be established or is not private to this user."""


class RuntimePathMissing(RuntimePathError):
    """The runtime directory (or a subdirectory) does not exist and was not to be created."""


class UnsafeRuntimePath(RuntimePathError):
    """A path is a link, belongs to someone else or is accessible by someone else."""


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


def runtime_directory() -> Path:
    """The per-user runtime directory (a pure path computation: nothing is created or checked)."""
    if _WINDOWS:
        return _windows_local_app_data() / WINDOWS_APP_DIRECTORY / WINDOWS_RUNTIME_DIRECTORY
    if _DARWIN:
        return _darwin_user_temp_directory() / ("%s%d" % (DIRECTORY_PREFIX, os.getuid()))
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(base) / ("%s%d" % (DIRECTORY_PREFIX, os.getuid()))


def _darwin_user_temp_directory() -> Path:
    try:
        value = os.confstr(_CS_DARWIN_USER_TEMP_DIR)
    except (ValueError, OSError):
        value = None
    return Path(value) if value else Path(tempfile.gettempdir())


def _windows_local_app_data() -> Path:
    """Known Folder LocalAppData; the environment and the home directory only if the API fails."""
    try:
        return Path(_known_local_app_data())
    except OSError:
        pass
    local = os.environ.get("LOCALAPPDATA")
    if local and os.path.isabs(local):
        return Path(local)
    return Path.home() / "AppData" / "Local"


# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------


def private_runtime_directory(*names: str, create: bool = True) -> Path:
    """The runtime directory (or a subdirectory of it), created if asked and validated private.

    Raises ``RuntimePathMissing`` when it is absent and ``create`` is false, ``UnsafeRuntimePath``
    when it is a link, owned by someone else or reachable by someone else, and ``RuntimePathError``
    for any other failure. Nothing is repaired except a directory of this user whose POSIX mode
    was looser than 0700.
    """
    path = runtime_directory()
    if create:
        os.makedirs(path.parent, exist_ok=True)
    _private_directory(path, create)
    for name in names:
        if not name or name in (".", "..") or os.sep in name or (os.altsep and os.altsep in name):
            raise ValueError("invalid runtime subdirectory name: %r" % (name,))
        path = path / name
        _private_directory(path, create)
    return path


def _private_directory(path: Path, create: bool) -> None:
    if _WINDOWS:
        _private_directory_windows(path, create)
    else:
        _private_directory_posix(path, create)


def _private_directory_posix(path: Path, create: bool) -> None:
    if create:
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise RuntimePathError("cannot create the runtime directory %s: %s" % (path, exc)) from exc
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise RuntimePathMissing("the runtime directory %s does not exist" % path) from exc
    except OSError as exc:
        # ELOOP: a symbolic link in place of the directory; ENOTDIR: something that is not a directory.
        raise UnsafeRuntimePath("the runtime path %s is not a plain directory: %s" % (path, exc)) from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            raise UnsafeRuntimePath("the runtime path %s is not a directory" % path)
        if info.st_uid != os.geteuid():
            raise UnsafeRuntimePath("the runtime directory %s belongs to another user (uid %d)" % (path, info.st_uid))
        if stat.S_IMODE(info.st_mode) & 0o077:
            # Ours but loose (a restrictive umask never produces this, a manual chmod does): tighten.
            os.fchmod(descriptor, 0o700)
            if stat.S_IMODE(os.fstat(descriptor).st_mode) & 0o077:
                raise UnsafeRuntimePath("the runtime directory %s stays accessible by others" % path)
    except OSError as exc:
        raise RuntimePathError("cannot validate the runtime directory %s: %s" % (path, exc)) from exc
    finally:
        os.close(descriptor)


def _private_directory_windows(path: Path, create: bool) -> None:
    if create and not path.exists():
        try:
            _create_windows_directory(path)
        except OSError as exc:
            raise RuntimePathError("cannot create the runtime directory %s: %s" % (path, exc)) from exc
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise RuntimePathMissing("the runtime directory %s does not exist" % path) from exc
    except OSError as exc:
        raise RuntimePathError("cannot inspect the runtime directory %s: %s" % (path, exc)) from exc
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
        raise UnsafeRuntimePath("the runtime path %s is not a plain directory (link or junction)" % path)
    try:
        _verify_windows_private(path)
    except OSError as exc:
        raise RuntimePathError("cannot validate the access rights of %s: %s" % (path, exc)) from exc


# ---------------------------------------------------------------------------
# Files (a private directory is required; these add no-follow and ownership checks)
# ---------------------------------------------------------------------------


def write_private_file(path: Path, data: bytes) -> None:
    """Create or atomically replace ``path`` (0600 on POSIX; the private directory's ACL on Windows)."""
    temporary = path.with_name("%s.%s.tmp" % (path.name, secrets.token_hex(4)))
    flags = (
        os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
        os.replace(temporary, path)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def read_private_file(path: Path, limit: int = MAX_FILE_BYTES) -> bytes:
    """Read a regular file of this user that nobody else can access (never through a link).

    ``FileNotFoundError`` propagates; links, foreign owners, loose modes and oversized files raise
    ``UnsafeRuntimePath``.
    """
    if _WINDOWS:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise UnsafeRuntimePath("%s is not a plain file" % path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise UnsafeRuntimePath("%s cannot be opened without following links: %s" % (path, exc)) from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise UnsafeRuntimePath("%s is not a regular file" % path)
        if not _WINDOWS and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
            raise UnsafeRuntimePath("%s is not private to this user" % path)
        if info.st_size > limit:
            raise UnsafeRuntimePath("%s is unexpectedly large" % path)
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            return handle.read(limit + 1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


# ---------------------------------------------------------------------------
# Windows: Known Folder, private directory creation and ACL validation (ctypes, advapi32/shell32)
# ---------------------------------------------------------------------------

_WIN32 = None

_SYSTEM_SID = "S-1-5-18"
# Deny, audit, alarm, mandatory-label, resource-attribute and scoped-policy ACEs never grant access.
_NON_GRANTING_ACE_TYPES = frozenset({1, 2, 3, 6, 7, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19})
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x1
_DACL_SECURITY_INFORMATION = 0x4
_TOKEN_QUERY = 0x8
_TOKEN_USER = 1
_TOKEN_OWNER = 4
_ERROR_ALREADY_EXISTS = 183
_SDDL_REVISION_1 = 1


def _win32():
    """ctypes prototypes for the few Win32 calls used here (declared once; pointers are 64-bit safe)."""
    global _WIN32
    if _WIN32 is not None:
        return _WIN32
    import ctypes
    from ctypes import wintypes
    from types import SimpleNamespace

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class Acl(ctypes.Structure):
        _fields_ = [
            ("AclRevision", ctypes.c_ubyte),
            ("Sbz1", ctypes.c_ubyte),
            ("AclSize", wintypes.WORD),
            ("AceCount", wintypes.WORD),
            ("Sbz2", wintypes.WORD),
        ]

    void_p = ctypes.c_void_p
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)

    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [void_p]
    kernel32.LocalFree.restype = void_p
    kernel32.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, void_p]
    kernel32.CreateDirectoryW.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [void_p, ctypes.POINTER(void_p)]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(void_p), void_p,
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(void_p), ctypes.POINTER(void_p), ctypes.POINTER(void_p), ctypes.POINTER(void_p),
        ctypes.POINTER(void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.GetAce.argtypes = [void_p, wintypes.DWORD, ctypes.POINTER(void_p)]
    advapi32.GetAce.restype = wintypes.BOOL
    shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(void_p)]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [void_p]
    ole32.CoTaskMemFree.restype = None

    _WIN32 = SimpleNamespace(
        ctypes=ctypes, wintypes=wintypes, kernel32=kernel32, advapi32=advapi32, shell32=shell32, ole32=ole32,
        GUID=GUID, SecurityAttributes=SecurityAttributes, Acl=Acl,
    )
    return _WIN32


def _known_local_app_data() -> str:
    """FOLDERID_LocalAppData {F1B32785-6FBA-4FCF-9D55-7B8E7F157091}, independent of the environment."""
    w = _win32()
    ctypes = w.ctypes
    guid = w.GUID(
        0xF1B32785, 0x6FBA, 0x4FCF,
        (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
    )
    path = ctypes.c_void_p()
    result = w.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path))
    try:
        if result < 0 or not path.value:
            raise OSError("SHGetKnownFolderPath(LocalAppData) failed: HRESULT 0x%08X" % (result & 0xFFFFFFFF))
        return ctypes.wstring_at(path.value)
    finally:
        if path.value:
            w.ole32.CoTaskMemFree(path)


def _sid_string(sid) -> str:
    w = _win32()
    ctypes = w.ctypes
    text = ctypes.c_void_p()
    if not w.advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.wstring_at(text.value)
    finally:
        w.kernel32.LocalFree(text)


def _token_sid(information_class: int) -> str:
    """SID text of TOKEN_USER or TOKEN_OWNER of this process (both start with the SID pointer)."""
    w = _win32()
    ctypes, wintypes = w.ctypes, w.wintypes
    token = wintypes.HANDLE()
    if not w.advapi32.OpenProcessToken(w.kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        needed = wintypes.DWORD(0)
        w.advapi32.GetTokenInformation(token, information_class, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not w.advapi32.GetTokenInformation(token, information_class, buffer, needed.value, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        return _sid_string(ctypes.c_void_p.from_buffer(buffer).value)
    finally:
        w.kernel32.CloseHandle(token)


def _create_windows_directory(path: Path) -> None:
    """Create ``path`` with a protected DACL: full control for this user and SYSTEM, nothing inherited."""
    w = _win32()
    ctypes = w.ctypes
    sddl = "D:P(A;OICI;FA;;;%s)(A;OICI;FA;;;SY)" % _token_sid(_TOKEN_USER)
    descriptor = ctypes.c_void_p()
    if not w.advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, _SDDL_REVISION_1, ctypes.byref(descriptor), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = w.SecurityAttributes(ctypes.sizeof(w.SecurityAttributes), descriptor.value, False)
        if not w.kernel32.CreateDirectoryW(str(path), ctypes.byref(attributes)):
            error = ctypes.get_last_error()
            if error != _ERROR_ALREADY_EXISTS:
                raise ctypes.WinError(error)
    finally:
        w.kernel32.LocalFree(descriptor)


def _verify_windows_private(path: Path) -> None:
    """Owner is this user (or the token's default owner, e.g. Administrators when elevated); the DACL
    exists and every access-granting entry names only this user or SYSTEM. Grants to any other
    account or group, and granting entry forms this code cannot interpret, are refused."""
    w = _win32()
    ctypes = w.ctypes
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    status = w.advapi32.GetNamedSecurityInfoW(
        str(path), _SE_FILE_OBJECT, _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
        ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(descriptor),
    )
    if status != 0:
        raise ctypes.WinError(status)
    try:
        trusted = {_token_sid(_TOKEN_USER), _token_sid(_TOKEN_OWNER)}
        allowed = {_token_sid(_TOKEN_USER), _SYSTEM_SID}
        owner_sid = _sid_string(owner.value)
        if owner_sid not in trusted:
            raise UnsafeRuntimePath("the runtime directory %s is owned by %s, not by this user" % (path, owner_sid))
        if not dacl.value:
            raise UnsafeRuntimePath("the runtime directory %s has no DACL (full access for everyone)" % path)
        acl = w.Acl.from_address(dacl.value)
        for index in range(acl.AceCount):
            ace = ctypes.c_void_p()
            if not w.advapi32.GetAce(dacl.value, index, ctypes.byref(ace)):
                raise ctypes.WinError(ctypes.get_last_error())
            ace_type, _flags, _size, mask = struct.unpack("<BBHI", ctypes.string_at(ace.value, 8))
            if ace_type in (0, 9):  # ACCESS_ALLOWED(_CALLBACK): the SID follows the mask.
                sid_offset = 8
            elif ace_type in (5, 11):  # ACCESS_ALLOWED_(CALLBACK_)OBJECT: optional GUIDs precede the SID.
                (object_flags,) = struct.unpack("<I", ctypes.string_at(ace.value + 8, 4))
                sid_offset = 12 + (16 if object_flags & 1 else 0) + (16 if object_flags & 2 else 0)
            elif ace_type in _NON_GRANTING_ACE_TYPES:
                continue
            else:
                raise UnsafeRuntimePath(
                    "the runtime directory %s has an access control entry of unsupported type %d" % (path, ace_type)
                )
            if not mask:
                continue
            sid = _sid_string(ace.value + sid_offset)
            if sid not in allowed:
                raise UnsafeRuntimePath("the runtime directory %s grants access to %s" % (path, sid))
    finally:
        w.kernel32.LocalFree(descriptor)
