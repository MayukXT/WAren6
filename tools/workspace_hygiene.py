"""Dry-run-first workspace organizer for WAren6 generated artifacts.

This tool deliberately moves only files and folders that match WAren6-generated
artifact names. It does not delete evidence and it does not touch source files.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CASE_DIR_RE = re.compile(r"^WAren6_\d{14}$", re.IGNORECASE)
CASE_ARCHIVE_RE = re.compile(
    r"^WAren6_\d{14}\.(?:zip|tar|tar\.zst|tar\.gz|tgz|tzst)$",
    re.IGNORECASE,
)
CASE_SIDECar_RE = re.compile(
    r"^WAren6_\d{14}(?:\.(?:zip|tar|tar\.zst|tar\.gz|tgz|tzst))?\.(?:sha256\.txt|md5\.txt|manifest\.json|logs\.txt)$",
    re.IGNORECASE,
)
TRANSFER_RE = re.compile(r"^WAren6_\d{14}\.telegram_transfer$", re.IGNORECASE)
UNIFIED_WORKSPACE_RE = re.compile(r".*_unified$", re.IGNORECASE)
LOCAL_MOCKUP_RE = re.compile(r".*_stitch\.html$", re.IGNORECASE)
CACHE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
BUILD_NAMES = {"target", "node_modules", "dist", "dist-ssr", "build"}
SCRATCH_NAMES = {"live-runtime-research"}
EVIDENCE_DIR_NAMES = {"localstate", "sessions"}
RUNTIME_DIR_NAMES = {"runtime"}
EVIDENCE_FILE_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".db-journal",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite-journal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
    ".ldb",
)


@dataclass(frozen=True)
class MoveItem:
    source: Path
    destination: Path
    kind: str

    def to_json(self, root: Path) -> dict[str, str]:
        return {
            "kind": self.kind,
            "source": self.source.relative_to(root).as_posix(),
            "destination": self.destination.relative_to(root).as_posix(),
        }


def classify_entry(path: Path) -> str | None:
    name = path.name
    if path.is_dir():
        if CASE_DIR_RE.match(name):
            return "case-directory"
        if TRANSFER_RE.match(name):
            return "telegram-transfer-directory"
        if UNIFIED_WORKSPACE_RE.match(name):
            return "unify-workspace"
        if name in CACHE_NAMES:
            return "cache-directory"
        if name in SCRATCH_NAMES:
            return "scratch-directory"
        lower_name = name.lower()
        if lower_name in RUNTIME_DIR_NAMES:
            return "runtime-directory"
        if lower_name in EVIDENCE_DIR_NAMES or lower_name.startswith("ebwebview"):
            return "evidence-directory"
        if name in BUILD_NAMES and path.parent.name in {"WAren6", "waren6-reader", "src-tauri"}:
            return "build-directory"
        return None

    lower_name = name.lower()
    if CASE_ARCHIVE_RE.match(name):
        return "case-archive"
    if CASE_SIDECar_RE.match(name):
        return "case-sidecar"
    if LOCAL_MOCKUP_RE.match(name):
        return "local-mockup"
    if lower_name.endswith(EVIDENCE_FILE_SUFFIXES):
        return "evidence-file"
    if lower_name.endswith(".jsonl"):
        return "runtime-jsonl"
    if ".bak" in name:
        return "backup-file"
    if name.endswith((".pyc", ".pyo")):
        return "python-cache"
    if name.endswith(".wa6enc") or ".part" in name:
        return "transfer-payload"
    return None


def destination_for(root: Path, path: Path, kind: str, artifacts_root: Path) -> Path:
    buckets = {
        "case-directory": "cases",
        "case-archive": "archives",
        "case-sidecar": "archives",
        "telegram-transfer-directory": "transfers",
        "transfer-payload": "transfers",
        "unify-workspace": "workspaces",
        "cache-directory": "caches",
        "python-cache": "caches",
        "build-directory": "build-output",
        "scratch-directory": "research",
        "evidence-directory": "evidence",
        "evidence-file": "evidence",
        "runtime-jsonl": "evidence",
        "runtime-directory": "evidence",
        "local-mockup": "references",
        "backup-file": "backups",
    }
    bucket = buckets.get(kind, "other")
    return root / artifacts_root / bucket / path.name


def iter_top_level_entries(root: Path) -> Iterable[Path]:
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if path.name == "artifacts":
            continue
        yield path


def build_move_plan(root: str | Path, artifacts_root: str | Path = "artifacts/local") -> list[MoveItem]:
    root = Path(root).resolve()
    artifacts_root = Path(artifacts_root)
    plan: list[MoveItem] = []
    for entry in iter_top_level_entries(root):
        kind = classify_entry(entry)
        if not kind:
            continue
        plan.append(MoveItem(entry, destination_for(root, entry, kind, artifacts_root), kind))
    return plan


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination
    for suffix in range(1, 1000):
        candidate = destination.with_name(f"{destination.name}-{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find a free destination near: {destination}")


def apply_move_plan(plan: Iterable[MoveItem], apply: bool = False) -> list[MoveItem]:
    moved: list[MoveItem] = []
    if not apply:
        return moved
    for item in plan:
        item.destination.parent.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(item.destination)
        shutil.move(str(item.source), str(destination))
        moved.append(MoveItem(item.source, destination, item.kind))
    return moved


def render_plan(root: Path, plan: list[MoveItem], apply: bool, json_output: bool) -> str:
    if json_output:
        return json.dumps(
            {
                "apply": apply,
                "planned_count": len(plan),
                "items": [item.to_json(root) for item in plan],
            },
            indent=2,
        )

    lines = [
        "WAren6 workspace hygiene plan",
        f"Root: {root}",
        f"Mode: {'apply' if apply else 'dry-run'}",
        "",
    ]
    if not plan:
        lines.append("No generated top-level artifacts matched the safe move rules.")
    for item in plan:
        lines.append(f"[{item.kind}] {item.source.name} -> {item.destination.relative_to(root)}")
    if not apply:
        lines.extend(("", "No files moved. Re-run with --apply to execute this plan."))
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize WAren6 generated workspace artifacts.")
    parser.add_argument("--root", default=".", help="Workspace root to inspect.")
    parser.add_argument(
        "--artifacts-root",
        default="artifacts/local",
        help="Relative destination root for generated artifacts.",
    )
    parser.add_argument("--apply", action="store_true", help="Move matched artifacts. Default is dry-run.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> str:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    plan = build_move_plan(root, args.artifacts_root)
    moved = apply_move_plan(plan, apply=args.apply)
    return render_plan(root, moved if args.apply else plan, args.apply, args.json)


def main() -> None:
    print(run_cli())


if __name__ == "__main__":
    main()
