"""Case folder/archive preparation for WAren6 unification."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tarfile


def _first_existing(*paths):
    for path in paths:
        if path and pathlib.Path(path).exists():
            return pathlib.Path(path)
    return None


def _is_waren6_archive(path):
    name = pathlib.Path(path).name.lower()
    return (
        name.endswith(".zip")
        or name.endswith(".tar")
        or name.endswith(".tar.gz")
        or name.endswith(".tgz")
        or name.endswith(".tar.zst")
        or name.endswith(".tzst")
    )


def _safe_extract_tar(tar, destination):
    destination = pathlib.Path(destination).resolve()
    for member in tar.getmembers():
        target = (destination / member.name).resolve()
        if not str(target).startswith(str(destination)):
            raise ValueError(f"Unsafe archive member path: {member.name}")
    tar.extractall(destination)


def _unpack_waren6_archive(archive_path, extract_root):
    archive_path = pathlib.Path(archive_path)
    extract_root = pathlib.Path(extract_root)
    name = archive_path.name.lower()
    if name.endswith(".zip"):
        shutil.unpack_archive(str(archive_path), str(extract_root), "zip")
        return
    if name.endswith(".tar.zst") or name.endswith(".tzst"):
        try:
            subprocess.run(
                ["tar", "-xf", str(archive_path), "-C", str(extract_root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(f"Unable to unpack zstd tar archive with system tar: {exc}") from exc
    with tarfile.open(archive_path, "r:*") as tar:
        _safe_extract_tar(tar, extract_root)


def prepare_unify_case(case_path, output_path=None):
    """Resolve folder/archive input into case paths used by the unifier."""
    original = pathlib.Path(case_path)
    if not original.exists():
        raise FileNotFoundError(f"Case path not found: {case_path}")

    extracted_from_zip = False
    extracted_from_archive = False
    extract_root = None
    if original.is_file() and _is_waren6_archive(original):
        stem = original.name
        for suffix in (".tar.zst", ".tar.gz", ".zip", ".tgz", ".tzst", ".tar"):
            if stem.lower().endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        base_dir = pathlib.Path(output_path).parent if output_path else original.parent / f"{stem}_unified"
        base_dir.mkdir(parents=True, exist_ok=True)
        extract_root = base_dir / "_source_case"
        if extract_root.exists():
            shutil.rmtree(extract_root)
        extract_root.mkdir(parents=True, exist_ok=True)
        _unpack_waren6_archive(original, extract_root)
        dirs = [p for p in extract_root.iterdir() if p.is_dir()]
        case_root = dirs[0] if len(dirs) == 1 and dirs[0].name.startswith("WAren6_") else extract_root
        extracted_from_zip = original.name.lower().endswith(".zip")
        extracted_from_archive = True
    else:
        case_root = original
        base_dir = pathlib.Path(output_path).parent if output_path else case_root

    idb_path = _first_existing(
        case_root / "EBWebView_Default",
        case_root / "EBWebView_Default" / "IndexedDB",
    )
    if not idb_path:
        raise FileNotFoundError(f"EBWebView IndexedDB evidence not found under {case_root}")

    output_db = pathlib.Path(output_path) if output_path else base_dir / "unified_whatsapp.db"
    output_db.parent.mkdir(parents=True, exist_ok=True)
    return {
        "case_root": case_root,
        "idb_path": idb_path,
        "decrypted_dir": case_root,
        "output": output_db,
        "extracted_from_zip": extracted_from_zip,
        "extracted_from_archive": extracted_from_archive,
        "extract_root": extract_root,
        "workspace": base_dir,
    }


def cleanup_prepared_unify_case(prepared, success=False):
    """Remove temporary extracted evidence only after a successful unify run."""
    if not prepared or not success:
        return
    extract_root = prepared.get("extract_root")
    if not extract_root:
        return
    extract_root = pathlib.Path(extract_root)
    if extract_root.exists() and extract_root.name == "_source_case":
        shutil.rmtree(extract_root)
