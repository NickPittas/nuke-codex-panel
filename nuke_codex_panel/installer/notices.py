"""Third-party license inventory for the installed private runtime.

Copies the actual LICENSE/NOTICE/COPYING/PATENTS files of every locked npm package (plus the
upstream texts listed in ``runtime/pi/notice-supplements.json`` where a published tarball ships
none), Node's own LICENSE and npm's LICENSE, and the project's license, into
``<runtime>/third-party-notices`` with an ``index.json``. A package whose license text cannot be
obtained is reported as unresolved, never counted as compliant on the strength of its
``license`` field. Licenses outside the manifest's allowed families fail the install.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from .common import InstallError, atomic_write, is_link_like

_NOTICE_NAME = re.compile(r"^(licen[sc]es?|notice|copying|patents|copyright|unlicen[sc]e)([-_. ].*)?$", re.I)
INDEX_SCHEMA = 2
_CODE_EXTENSIONS = {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".tsx", ".jsx", ".map", ".py", ".json", ".css", ".html"}


def _safe(name: str) -> str:
    return name.replace("/", "__")


def _named_dir_files(directory: Path) -> list:
    files = []
    for root, dirs, names in os.walk(str(directory)):
        dirs[:] = sorted(d for d in dirs if not is_link_like(Path(root, d)))
        files.extend(Path(root, n) for n in sorted(names) if not is_link_like(Path(root, n)))
    return sorted(files, key=str)


def notice_files(directory: Path, nested: bool = True) -> list:
    """License-like files in ``directory``, in license-named subdirectories and (``nested``) in any
    ordinary subdirectory such as ``src/_vendor/x``. Symlinks and ``node_modules`` (indexed on their
    own) are skipped."""
    found = []
    pending = [Path(directory)]
    while pending:
        current = pending.pop(0)
        try:
            entries = sorted(os.scandir(str(current)), key=lambda e: e.name)
        except OSError as exc:
            raise InstallError("cannot scan {} for license files: {}".format(current, exc)) from exc
        for entry in entries:
            path = Path(entry.path)
            if is_link_like(path):
                continue
            named = bool(_NOTICE_NAME.match(entry.name))
            if entry.is_file(follow_symlinks=False):
                if named and os.path.splitext(entry.name)[1].lower() not in _CODE_EXTENSIONS:
                    found.append(path)
            elif entry.is_dir(follow_symlinks=False):
                if named:
                    found.extend(_named_dir_files(path))
                elif nested and entry.name not in ("node_modules", ".git"):
                    pending.append(path)
    return sorted(set(found), key=str)


def _license_expression(meta: dict, lock_entry: dict) -> str:
    value = meta.get("license", lock_entry.get("license"))
    if value is None and meta.get("licenses"):
        value = meta["licenses"]
    if isinstance(value, dict):
        value = value.get("type")
    if isinstance(value, list):
        parts = [(item.get("type") if isinstance(item, dict) else str(item)) for item in value]
        value = " OR ".join(p for p in parts if p)
    return value.strip() if isinstance(value, str) else ""


def license_allowed(expression: str, allowed) -> bool:
    """Evaluate an SPDX expression: OR needs one allowed side, AND needs all, WITH is ignored."""
    allowed = {item.lower() for item in allowed}
    tokens = re.findall(r"\(|\)|[^\s()]+", expression)
    position = 0

    def peek():
        return tokens[position].upper() if position < len(tokens) else None

    def term():
        nonlocal position
        if position >= len(tokens):
            raise ValueError("unexpected end")
        token = tokens[position]
        if token == "(":
            position += 1
            result = disjunction()
            if peek() != ")":
                raise ValueError("missing )")
            position += 1
            return result
        if token in (")",) or token.upper() in ("AND", "OR", "WITH"):
            raise ValueError("unexpected " + token)
        position += 1
        if peek() == "WITH":
            position += 2
        return token.rstrip("+").lower() in allowed

    def conjunction():
        nonlocal position
        result = term()
        while peek() == "AND":
            position += 1
            result = term() and result
        return result

    def disjunction():
        nonlocal position
        result = conjunction()
        while peek() == "OR":
            position += 1
            result = conjunction() or result
        return result

    if not tokens:
        return False
    try:
        result = disjunction()
    except ValueError:
        return False
    return result and position == len(tokens)


def _copy(source: Path, destination: Path) -> str:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
    except OSError as exc:
        raise InstallError("cannot copy notice file {}: {}".format(source, exc)) from exc
    return destination.name


def generate_notices(
    *,
    runtime_dir: Path,
    project_root: Path,
    manifest: dict,
    node_spec: dict,
    out_dir: Path,
) -> dict:
    """Write ``out_dir`` and return the index (also stored as ``out_dir/index.json``).

    ``runtime_dir`` holds ``node_modules``/``package-lock.json``/``node``; ``project_root`` holds the
    project LICENSE and the supplement files; ``out_dir`` must not exist yet.
    """
    allowed = manifest["notices"]["allowed_licenses"]
    lock = json.loads((runtime_dir / "package-lock.json").read_text(encoding="utf-8"))
    supplements_path = project_root / "runtime" / "pi" / "notice-supplements.json"
    supplements = {"supplements": [], "unresolved": []}
    if supplements_path.is_file():
        supplements = json.loads(supplements_path.read_text(encoding="utf-8"))
    supplied_by_name = {}
    for group in supplements.get("supplements", []):
        for name in group["packages"]:
            supplied_by_name.setdefault(name, []).append(group)
    unresolved_by_name = {item["package"]: item for item in supplements.get("unresolved", [])}

    out_dir.mkdir(parents=True)
    packages, disallowed, seen = [], [], {}
    for key in sorted(lock.get("packages", {})):
        if not key:
            continue
        entry = lock["packages"][key]
        if entry.get("link"):
            continue
        package_dir = runtime_dir.joinpath(*key.split("/"))
        if not (package_dir / "package.json").is_file():
            if entry.get("optional"):
                continue
            raise InstallError("locked package {} is not installed at {}".format(key, package_dir))
        meta = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
        name = meta.get("name") or key.rsplit("node_modules/", 1)[-1]
        version = meta.get("version") or entry.get("version") or "unknown"
        identity = "{}@{}".format(name, version)
        expression = _license_expression(meta, entry)
        if identity in seen:
            seen[identity]["installed_at"].append(key)
            continue
        if not license_allowed(expression, allowed):
            disallowed.append("{} ({})".format(identity, expression or "no license declared"))

        record = {
            "name": name,
            "version": version,
            "license": expression,
            "installed_at": [key],
            "license_files": [],
            "supplied_files": [],
            "status": "unresolved",
        }
        destination = out_dir / "npm" / "{}@{}".format(_safe(name), version)
        for source in notice_files(package_dir):
            relative = source.relative_to(package_dir).as_posix()
            _copy(source, destination / relative)
            record["license_files"].append("npm/{}@{}/{}".format(_safe(name), version, relative))
        for group in supplied_by_name.get(name, []):
            for item in group["files"]:
                source = project_root / item["path"]
                if not source.is_file():
                    raise InstallError("license supplement file missing: {}".format(source))
                target = destination / item["name"]
                if target.exists():
                    raise InstallError("license supplement {} collides with a packaged file".format(target))
                _copy(source, target)
                record["supplied_files"].append("npm/{}@{}/{}".format(_safe(name), version, item["name"]))
            record["supplied_license"] = group["license"]
            record["supplied_source"] = group["source"]
        unresolved = unresolved_by_name.get(name)
        if unresolved:
            record["note"] = unresolved["note"]
            record["declared_author"] = meta.get("author")
            record["evidence_files"] = []
            for evidence in ("package.json", "README.md", "README", "readme.md"):
                source = package_dir / evidence
                if source.is_file():
                    _copy(source, destination / ("EVIDENCE-" + evidence))
                    record["evidence_files"].append(
                        "npm/{}@{}/EVIDENCE-{}".format(_safe(name), version, evidence)
                    )
            record["status"] = "unresolved"
        elif record["license_files"] or record["supplied_files"]:
            record["status"] = "included" if record["license_files"] else "supplied"
        seen[identity] = record
        packages.append(record)

    if disallowed:
        raise InstallError(
            "installed packages use licenses outside the allowed families ({}): {}".format(
                ", ".join(allowed), "; ".join(disallowed)
            )
        )

    node_dir = runtime_dir / manifest["node"]["install_dir"]
    node_license = node_dir / "LICENSE"
    if not node_license.is_file():
        raise InstallError("Node LICENSE missing from {}".format(node_dir))
    _copy(node_license, out_dir / "node" / "LICENSE")
    npm_dir = node_dir.joinpath(*node_spec["npm_cli"].split("/")).parents[1]
    npm_files = notice_files(npm_dir, nested=False)
    npm_names = [_copy(p, out_dir / "node" / ("npm-" + p.name)) for p in npm_files if p.parent == npm_dir]
    if not npm_names:
        raise InstallError("npm LICENSE missing from {}".format(npm_dir))

    project = {}
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        source = project_root / name
        if source.is_file():
            project[name] = "project/" + _copy(source, out_dir / "project" / name)
    if "LICENSE" not in project:
        raise InstallError("project LICENSE missing from {}".format(project_root))

    unresolved_report = sorted(r["name"] + "@" + r["version"] for r in packages if r["status"] == "unresolved")
    index = {
        "schema": INDEX_SCHEMA,
        "allowed_licenses": list(allowed),
        "node": {
            "version": manifest["node"]["version"],
            "license_file": "node/LICENSE",
            "npm_license_files": ["node/" + name for name in npm_names],
            "note": "Node's LICENSE carries the notices of the components bundled in Node; npm's own "
            "bundled dependencies keep their license files in place under the installed node directory.",
        },
        "project": project,
        "summary": {
            "packages": len(packages),
            "with_own_license_files": sum(1 for r in packages if r["license_files"]),
            "supplied_from_upstream": sum(1 for r in packages if r["status"] == "supplied"),
            "unresolved": len(unresolved_report),
        },
        "unresolved": unresolved_report,
        "packages": packages,
        "files": _hash_tree(out_dir),
    }
    atomic_write(out_dir / "index.json", (json.dumps(index, indent=2) + "\n").encode("utf-8"))
    return index


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_tree(root: Path) -> dict:
    hashes = {}
    for base, _dirs, names in os.walk(str(root)):
        for name in names:
            path = Path(base, name)
            relative = path.relative_to(root).as_posix()
            if relative != "index.json":
                hashes[relative] = _sha256(path)
    return dict(sorted(hashes.items()))


def verify_notices(notices_dir: Path, runtime_dir: Path, manifest: dict) -> list:
    """Offline problems: every file the index references exists and matches its recorded hash, and
    Node's own LICENSE matches the installed one. Empty list = good."""
    try:
        index = json.loads((notices_dir / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["license index unreadable: {}".format(exc)]
    hashes = index.get("files")
    if not isinstance(hashes, dict) or index.get("schema") != INDEX_SCHEMA:
        return ["license inventory was written by an older installer; re-run the installer to regenerate it"]
    referenced = []
    node = index.get("node") or {}
    referenced.append(node.get("license_file"))
    referenced.extend(node.get("npm_license_files") or [])
    referenced.extend((index.get("project") or {}).values())
    for record in index.get("packages") or []:
        for key in ("license_files", "supplied_files", "evidence_files"):
            referenced.extend(record.get(key) or [])
    problems = []
    for relative in sorted({r for r in referenced if r}):
        path = notices_dir.joinpath(*relative.split("/"))
        if relative not in hashes:
            problems.append("license inventory has no hash for {}".format(relative))
        elif not path.is_file():
            problems.append("referenced notice file missing: {}".format(relative))
        elif _sha256(path) != hashes[relative]:
            problems.append("notice file changed since install: {}".format(relative))
    for relative, expected in hashes.items():
        if relative not in referenced and not notices_dir.joinpath(*relative.split("/")).is_file():
            problems.append("notice file missing: {}".format(relative))
    node_license = runtime_dir / manifest["node"]["install_dir"] / "LICENSE"
    copied = notices_dir / "node" / "LICENSE"
    if node_license.is_file() and copied.is_file() and _sha256(node_license) != _sha256(copied):
        problems.append("Node LICENSE differs from the installed Node's LICENSE")
    return problems
