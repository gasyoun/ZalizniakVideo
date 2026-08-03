#!/usr/bin/env python3
"""Transactionally sync the BookIndex public v2 video catalog.

The command builds and validates a temporary repository copy first.  Only a
fully valid candidate is copied into the checkout.  Drift is emitted as an
actionable binary Git patch; this command never commits or opens a PR.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_URL = "https://raw.githubusercontent.com/gasyoun/BookIndex/main/data/video_catalog_public.v2.json"
DEFAULT_ARTIFACT = ROOT / ".sync-artifacts" / "bookindex-video-v2.patch"
DEFAULT_AUDIT = ROOT / ".sync-artifacts" / "bookindex-video-v2-sync.json"
GENERATED_PATHS = (
    ".nojekyll",
    "assets/thumbs",
    "data/catalog.json",
    "data/catalog.v2.json",
    "data/stats.json",
    "index.html",
    "robots.txt",
    "sitemap.xml",
    "v",
    "video",
)
EVIDENCE_SUPPORTS = {
    "title_display",
    "contributors",
    "date_recorded",
    "upload_date",
    "topics",
    "type",
    "purpose",
    "transcript_status",
    "transcript_url",
    "public_note",
}
CONTRIBUTOR_ROLES = {"speaker", "lecturer", "interviewer", "moderator", "participant", "host"}

sys.path.insert(0, str(ROOT / "scripts"))
import build_site  # noqa: E402
import validate_site  # noqa: E402


class SyncError(ValueError):
    """An actionable, expected sync failure."""


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ZalizniakVideo BookIndex sync/1"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as error:
        raise SyncError(f"download failed for {url}: {error}") from error


def validate_export(raw: bytes) -> tuple[dict, str]:
    checksum = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncError(f"malformed public export: {error}") from error
    if not isinstance(payload, dict):
        raise SyncError("malformed public export: root must be an object")
    schema = payload.get("schema")
    version = payload.get("version")
    if schema != "video_catalog_public/2" or version != 2:
        raise SyncError(f"expected BookIndex public schema v2, found schema={schema!r} version={version!r}")
    if not isinstance(payload.get("built_at"), str):
        raise SyncError("malformed public export: built_at must be an ISO date-time string")
    required_containers = {"source": dict, "stats": dict, "videos": list, "unresolved_records": list, "related_resources": list}
    for key, expected_type in required_containers.items():
        if not isinstance(payload.get(key), expected_type):
            raise SyncError(f"malformed public export: {key} must be {expected_type.__name__}")
    records = payload["videos"]
    source = payload["source"]
    source_string_keys = ("sheet_url", "sheet_gid", "snapshot_file", "snapshot_at", "accession_registry", "editorial_file")
    if not all(isinstance(source.get(key), str) and source[key] for key in source_string_keys):
        raise SyncError("malformed public export: source metadata is incomplete")
    if not re.match(r"^https?://", source["sheet_url"]):
        raise SyncError("malformed public export: source.sheet_url must be HTTP(S)")
    if source["editorial_file"] != "data/video_catalog_editorial.json":
        raise SyncError("malformed public export: unexpected source.editorial_file")
    if not isinstance(source.get("canonical_inputs"), list) or not all(isinstance(value, str) and value for value in source["canonical_inputs"]):
        raise SyncError("malformed public export: source.canonical_inputs must be an array of strings")
    stat_keys = {"source_rows", "videos", "unique_youtube_ids", "unresolved_records", "related_resources"}
    if not stat_keys.issubset(payload["stats"]) or not all(isinstance(payload["stats"][key], int) and payload["stats"][key] >= 0 for key in stat_keys):
        raise SyncError("malformed public export: stats must contain the five required non-negative integer v2 counters")
    expected_count = payload["stats"]["videos"]
    if expected_count != len(records):
        raise SyncError(f"malformed public export: stats.videos={expected_count} but videos has {len(records)} records")
    if payload["stats"]["unique_youtube_ids"] != len(records):
        raise SyncError("malformed public export: stats.unique_youtube_ids differs from videos")
    if payload["stats"]["unresolved_records"] != len(payload["unresolved_records"]):
        raise SyncError("malformed public export: unresolved_records count differs from stats")
    if payload["stats"]["related_resources"] != len(payload["related_resources"]):
        raise SyncError("malformed public export: related_resources count differs from stats")
    accessions: set[str] = set()
    youtube_ids: set[str] = set()
    for position, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise SyncError(f"record {position}: expected an object")
        accession = str(record.get("accession") or "")
        youtube_id = build_site.youtube_id(record.get("youtube_id"))
        watch_id = build_site.youtube_id(record.get("watch_url"))
        label = accession or f"row {position}"
        if not re.fullmatch(r"\d{3}", accession):
            raise SyncError(f"record {label}: invalid or missing accession")
        if not youtube_id:
            raise SyncError(f"record {accession}: invalid or missing youtube_id")
        if watch_id != youtube_id:
            raise SyncError(f"record {accession}: watch_url does not match youtube_id {youtube_id}")
        if accession in accessions:
            raise SyncError(f"record {accession}: duplicate accession")
        if youtube_id in youtube_ids:
            raise SyncError(f"record {accession}: duplicate youtube_id {youtube_id}")
        accessions.add(accession)
        youtube_ids.add(youtube_id)
        contributors = record.get("contributors", [])
        if not isinstance(contributors, list):
            raise SyncError(f"record {accession}: contributors must be an array")
        for contributor_number, contributor in enumerate(contributors, 1):
            if not isinstance(contributor, dict) or not isinstance(contributor.get("name"), str) or not contributor["name"].strip():
                raise SyncError(f"record {accession}: contributor {contributor_number} requires a non-empty name")
            if contributor.get("role") not in CONTRIBUTOR_ROLES:
                raise SyncError(f"record {accession}: contributor {contributor_number} has unknown role {contributor.get('role')!r}")
        evidence = record.get("evidence", [])
        if not isinstance(evidence, list):
            raise SyncError(f"record {accession}: evidence must be an array")
        evidence_dates: list[str] = []
        for item_number, item in enumerate(evidence, 1):
            if not isinstance(item, dict):
                raise SyncError(f"record {accession}: evidence {item_number} must be an object")
            url = item.get("url")
            label_text = item.get("label")
            if not isinstance(url, str) or not re.match(r"^https?://", url) or not isinstance(label_text, str) or not label_text.strip():
                raise SyncError(f"record {accession}: evidence {item_number} requires public HTTP(S) url and non-empty label")
            accessed_at = item.get("accessed_at")
            if not isinstance(accessed_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", accessed_at):
                raise SyncError(f"record {accession}: evidence {item_number} has invalid accessed_at")
            try:
                dt.date.fromisoformat(accessed_at)
            except ValueError as error:
                raise SyncError(f"record {accession}: evidence {item_number} has invalid accessed_at {accessed_at}") from error
            evidence_dates.append(accessed_at)
            supports = item.get("supports")
            if not isinstance(supports, list) or not supports or not all(isinstance(value, str) and value in EVIDENCE_SUPPORTS for value in supports):
                raise SyncError(f"record {accession}: evidence {item_number} supports contains a forbidden or unknown field")
            if len(set(supports)) != len(supports):
                raise SyncError(f"record {accession}: evidence {item_number} supports contains duplicates")
        expected_verified = max(evidence_dates) if evidence_dates else None
        if record.get("last_verified_at") != expected_verified:
            raise SyncError(f"record {accession}: last_verified_at must be {expected_verified!r} from evidence")
    return payload, checksum


def write_audit(path: Path, payload: dict, checksum: str, source: str) -> None:
    videos = payload.get("videos", [])
    audit = {
        "source": source,
        "schema": payload["schema"],
        "version": payload["version"],
        "sha256": checksum,
        "records": len(videos),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_repository(source: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(".git", ".sync-artifacts", "__pycache__", "*.pyc")
    shutil.copytree(source, destination, ignore=ignored)


def run_quality_checks(candidate: Path) -> None:
    commands = (
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "scripts/validate_site.py", "--root", str(candidate)],
    )
    for command in commands:
        result = subprocess.run(command, cwd=candidate, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            raise SyncError(f"validation command failed ({result.returncode}): {' '.join(command)}")


def same_path(left: Path, right: Path) -> bool:
    if left.is_file() != right.is_file() or left.is_dir() != right.is_dir():
        return False
    if not left.exists() and not right.exists():
        return True
    if left.is_file():
        return left.read_bytes() == right.read_bytes()
    left_files = {path.relative_to(left).as_posix(): path for path in left.rglob("*") if path.is_file()}
    right_files = {path.relative_to(right).as_posix(): path for path in right.rglob("*") if path.is_file()}
    return left_files.keys() == right_files.keys() and all(left_files[name].read_bytes() == right_files[name].read_bytes() for name in left_files)


def changed_paths(root: Path, candidate: Path) -> list[str]:
    return [name for name in GENERATED_PATHS if not same_path(root / name, candidate / name)]


def replace_paths_transactionally(root: Path, candidate: Path, paths: list[str], backup_root: Path) -> None:
    completed: list[str] = []
    try:
        for name in paths:
            current = root / name
            incoming = candidate / name
            backup = backup_root / name
            if current.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(current), str(backup))
            completed.append(name)
            if incoming.is_dir():
                shutil.copytree(incoming, current)
            elif incoming.is_file():
                current.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(incoming, current)
    except OSError:
        restore_paths(root, completed, backup_root)
        raise


def restore_paths(root: Path, paths: list[str], backup_root: Path) -> None:
    for name in reversed(paths):
        current = root / name
        backup = backup_root / name
        if current.is_dir():
            shutil.rmtree(current)
        elif current.exists():
            current.unlink()
        if backup.exists():
            current.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(backup), str(current))


def binary_patch(root: Path, artifact: Path, paths: list[str], temp_root: Path) -> None:
    if not (root / ".git").exists():
        raise SyncError("cannot create binary patch: checkout has no .git directory")
    index = temp_root / "git-index"
    index_lookup = subprocess.run(
        ["git", "rev-parse", "--git-path", "index"],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if index_lookup.returncode:
        raise SyncError(f"cannot locate Git index: {index_lookup.stderr.strip()}")
    source_index = Path(index_lookup.stdout.strip())
    if not source_index.is_absolute():
        source_index = root / source_index
    if source_index.is_file():
        shutil.copy2(source_index, index)
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(index)
    add = subprocess.run(["git", "add", "-A", "--", *paths], cwd=root, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if add.returncode:
        raise SyncError(f"cannot stage temporary patch index: {add.stderr.strip()}")
    diff = subprocess.run(["git", "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "--", *paths], cwd=root, env=env, capture_output=True)
    if diff.returncode:
        raise SyncError(f"cannot create binary patch (git diff exit {diff.returncode})")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(diff.stdout)


def sync(
    root: Path,
    raw: bytes,
    artifact: Path,
    *,
    quality_checks: Callable[[Path], None] = run_quality_checks,
    temp_parent: Path | None = None,
) -> list[str]:
    payload, _checksum = validate_export(raw)
    if artifact.exists():
        artifact.unlink()
    with tempfile.TemporaryDirectory(prefix="zaliz-video-sync-", dir=temp_parent) as directory:
        temp_root = Path(directory)
        candidate = temp_root / "candidate"
        copy_repository(root, candidate)
        staged_input = temp_root / "video_catalog_public.v2.json"
        staged_input.write_bytes(raw)
        records, source_meta = build_site.normalize_records(payload)
        if not records:
            raise SyncError("public export contains no usable YouTube records")
        thumb_root = candidate / "assets" / "thumbs"
        build_site.fetch_thumbnails(records, thumb_root)
        try:
            build_site.validate(records, thumb_root)
        except ValueError as error:
            raise SyncError(str(error)) from error
        legacy_meta = json.loads((root / "data" / "catalog.json").read_text(encoding="utf-8"))
        build_site.write_site(records, source_meta, candidate, legacy_meta)
        try:
            validate_site.validate(candidate)
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
            raise SyncError(f"release validation failed: {error}") from error
        quality_checks(candidate)
        paths = changed_paths(root, candidate)
        if not paths:
            return []
        backup_root = temp_root / "backup"
        replace_paths_transactionally(root, candidate, paths, backup_root)
        try:
            binary_patch(root, artifact, paths, temp_root)
        except (OSError, SyncError):
            restore_paths(root, paths, backup_root)
            raise
        return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--catalog", type=Path, help="local public v2 export (testing/manual recovery)")
    source.add_argument("--url", default=DEFAULT_CATALOG_URL, help="raw BookIndex public v2 URL")
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT, help="binary patch output")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT, help="raw-export integrity metadata")
    parser.add_argument("--fail-on-drift", action="store_true", help="return exit 2 after producing a drift patch")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        for stale in (args.artifact, args.audit):
            if stale.exists():
                stale.unlink()
        if args.catalog:
            raw = args.catalog.read_bytes()
            source = str(args.catalog)
        else:
            raw = download(args.url)
            source = args.url
        payload, checksum = validate_export(raw)
        write_audit(args.audit, payload, checksum, source)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(f"## BookIndex video v2 sync\n\n- SHA-256: `{checksum}`\n- Records: {len(payload.get('videos', []))}\n- Source: `{source}`\n")
        print(f"BookIndex raw SHA-256: {checksum}")
        changed = sync(ROOT, raw, args.artifact)
    except (OSError, SyncError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not changed:
        print("OK: BookIndex v2 is valid; generated site has no drift")
        return 0
    print(f"DRIFT: {', '.join(changed)}")
    print(f"Binary patch: {args.artifact}")
    print(f"Review with: git apply --stat {args.artifact}")
    print(f"Apply elsewhere with: git apply --binary {args.artifact}")
    return 2 if args.fail_on_drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
