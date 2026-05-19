"""Build a WAren6 end-user field kit.

The builder copies only the runtime scripts, operator docs, runtime DLLs,
optional wheels, and optional embedded Python. Developer-only source, tests,
generated evidence, caches, archives, and build output are excluded.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path


PACKAGE_ROOT = "WAren6-FieldKit"
MANIFEST_NAME = "WAren6.fieldkit.manifest.json"
CORE_FILES = (
    "BouncyCastle.Cryptography.dll",
    "fieldkit-version.json",
    "LLM.txt",
    "requirements-lock.txt",
    "version.json",
    "waren6.ps1",
    "waren6.py",
    "waren6_unify_case.py",
)
AIRGAP_FILES = (
    "airgap/README.md",
    "airgap/dependency-notices.md",
    "airgap/install-offline-deps.ps1",
)
OPTIONAL_DIRS = ("wheels", "python_embedded")
EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".github",
    "node_modules",
    "target",
    "artifacts",
    "tests",
    "tools",
    "waren6-reader",
    "LocalState",
    "sessions",
}
EXCLUDED_SUFFIXES = (
    ".bak",
    ".pyc",
    ".pyo",
    ".db",
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".sqlite",
    ".sqlite-wal",
    ".sqlite-shm",
    ".sqlite-journal",
    ".sqlite3",
    ".sqlite3-wal",
    ".sqlite3-shm",
    ".dec.db",
    ".dec.db-wal",
    ".dec.db-shm",
    ".jsonl",
    ".zip",
    ".tar.zst",
    ".tar.gz",
    ".tgz",
    ".tzst",
    ".wa6enc",
)
EXCLUDED_FILENAMES = {
    "BREAKTHROUGHS.md",
    "FORME.md",
    "RESEARCH.md",
}


@dataclass(frozen=True)
class PackageFile:
    source: Path
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class PackageResult:
    archive_path: Path
    sha256_path: Path
    manifest_path: Path
    file_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_generated_path(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_PARTS:
        return True
    name = path.name
    if name in EXCLUDED_FILENAMES:
        return True
    if name.startswith("WAren6_"):
        return True
    if name.lower().startswith("ebwebview"):
        return True
    if name.endswith("_stitch.html"):
        return True
    if ".bak" in name:
        return True
    return name.endswith(EXCLUDED_SUFFIXES)


def add_file(plan: dict[str, PackageFile], root: Path, path: Path, relative_path: str) -> None:
    if not path.exists() or not path.is_file() or is_generated_path(path.relative_to(root)):
        return
    normalized = relative_path.replace("\\", "/")
    plan[normalized] = PackageFile(
        source=path,
        relative_path=normalized,
        size=path.stat().st_size,
        sha256=sha256_file(path),
    )


def add_dir(plan: dict[str, PackageFile], root: Path, directory: Path, base_relative: str) -> None:
    if not directory.exists() or not directory.is_dir():
        return
    for file_path in sorted(directory.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root)
        if is_generated_path(relative):
            continue
        add_file(plan, root, file_path, str(relative))


def build_file_plan(root: str | Path, include_reader: bool = False) -> list[PackageFile]:
    root = Path(root).resolve()
    plan: dict[str, PackageFile] = {}

    for relative in CORE_FILES:
        add_file(plan, root, root / relative, relative)
    for relative in AIRGAP_FILES:
        add_file(plan, root, root / relative, relative)
    for relative in OPTIONAL_DIRS:
        add_dir(plan, root, root / relative, relative)
    if include_reader:
        raise ValueError("Reader source is not part of the end-user field kit. Use the Reader release assets instead.")

    return [plan[key] for key in sorted(plan)]


def write_fieldkit_readme(stage_root: Path) -> Path:
    readme = """# WAren6 Field Kit

This package contains the files needed to run WAren6 without cloning the GitHub repository.

## First Run

Open PowerShell in this folder and preview what WAren6 will do:

```powershell
powershell -ExecutionPolicy Bypass -File .\\waren6.ps1 --dry
```

Run the preflight check:

```powershell
powershell -ExecutionPolicy Bypass -File .\\waren6.ps1 -doc
```

Run the default hybrid extraction on an authorized logged-in WhatsApp Desktop machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\\waren6.ps1
```

For strict offline/no-network use:

```powershell
powershell -ExecutionPolicy Bypass -File .\\waren6.ps1 -f --no-net
```

## Offline Dependencies

If this package includes `wheels\\`, install Python dependencies without internet:

```powershell
powershell -ExecutionPolicy Bypass -File .\\airgap\\install-offline-deps.ps1
```

## Reader

Download WAren6 Reader separately from:

https://github.com/MayukXT/WAren6/releases?q=reader-v&expanded=true
"""
    path = stage_root / "README_FIELDKIT.md"
    path.write_text(readme, encoding="utf-8")
    return path


def write_manifest(stage_root: Path, files: list[PackageFile], include_reader: bool) -> Path:
    manifest = {
        "schema": "waren6.fieldkit.manifest.v1",
        "tool": "WAren6",
        "generated_at_utc": _dt.datetime.now(_dt.UTC).isoformat(),
        "package_root": PACKAGE_ROOT,
        "include_reader": include_reader,
        "file_count": len(files),
        "files": [
            {
                "path": item.relative_path,
                "size": item.size,
                "sha256": item.sha256,
            }
            for item in files
        ],
        "offline_commands": [
            "powershell -ExecutionPolicy Bypass -File .\\waren6.ps1 -f --no-net",
            "powershell -ExecutionPolicy Bypass -File .\\waren6.ps1 -f -w C:\\Cases\\CollectedLocalState -i <oduid-hex> --no-net",
            "python waren6.py --unify C:\\Cases\\WAren6_<timestamp>.tar.zst --with-media-index",
        ],
    }
    manifest_path = stage_root / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def copy_files(stage_root: Path, files: list[PackageFile]) -> None:
    for item in files:
        destination = stage_root / item.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, destination)


def build_package(
    root: str | Path,
    output_dir: str | Path,
    include_reader: bool = False,
    package_name: str | None = None,
) -> PackageResult:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = package_name or f"WAren6-FieldKit-{_dt.datetime.now().strftime('%Y%m%d%H%M%S')}"

    files = build_file_plan(root, include_reader=include_reader)
    if not files:
        raise RuntimeError("No files matched the airgap package plan.")

    stage_parent = output_dir / f"{package_name}.stage"
    stage_root = stage_parent / PACKAGE_ROOT
    if stage_parent.exists():
        shutil.rmtree(stage_parent)
    stage_root.mkdir(parents=True)

    try:
        copy_files(stage_root, files)
        write_fieldkit_readme(stage_root)
        manifest_path = write_manifest(stage_root, files, include_reader)
        archive_path = output_dir / f"{package_name}.zip"
        if archive_path.exists():
            archive_path.unlink()
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(stage_root.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(stage_parent))
        archive_hash = sha256_file(archive_path)
        sha256_path = output_dir / f"{package_name}.sha256.txt"
        sha256_path.write_text(f"{archive_hash}  {archive_path.name}\n", encoding="utf-8")
        return PackageResult(
            archive_path=archive_path,
            sha256_path=sha256_path,
            manifest_path=manifest_path,
            file_count=len(files) + 2,
        )
    finally:
        shutil.rmtree(stage_parent, ignore_errors=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a WAren6 air-gapped package.")
    parser.add_argument("--root", default=".", help="WAren6 source root.")
    parser.add_argument("--output", default="dist/airgap", help="Package output directory.")
    parser.add_argument("--name", help="Package base name without extension.")
    parser.add_argument("--include-reader", action="store_true", help="Reserved for compatibility; Reader source is not packaged.")
    parser.add_argument("--json", action="store_true", help="Print package result as JSON.")
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> str:
    args = parse_args(argv)
    result = build_package(
        root=args.root,
        output_dir=args.output,
        include_reader=args.include_reader,
        package_name=args.name,
    )
    if args.json:
        return json.dumps(
            {
                "archive": str(result.archive_path),
                "sha256": str(result.sha256_path),
                "file_count": result.file_count,
            },
            indent=2,
        )
    return "\n".join(
        [
            f"Archive: {result.archive_path}",
            f"SHA-256: {result.sha256_path}",
            f"Files: {result.file_count}",
        ]
    )


def main() -> None:
    print(run_cli())


if __name__ == "__main__":
    main()
