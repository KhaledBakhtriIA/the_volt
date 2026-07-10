from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class RetentionPolicy:
    """Retention windows in days per dataset tier."""

    raw_days: int
    processed_days: int
    exports_days: int
    archive_days: int


@dataclass
class RetentionResult:
    """Structured execution output for observability and automation."""

    archived: int = 0
    deleted: int = 0
    archived_bytes: int = 0
    deleted_bytes: int = 0
    pruned_archive: int = 0
    pruned_archive_bytes: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "archived": self.archived,
            "deleted": self.deleted,
            "archived_bytes": self.archived_bytes,
            "deleted_bytes": self.deleted_bytes,
            "pruned_archive": self.pruned_archive,
            "pruned_archive_bytes": self.pruned_archive_bytes,
        }


def _build_policy() -> RetentionPolicy:
    return RetentionPolicy(
        raw_days=_env_int("DATA_API_RETENTION_RAW_DAYS", 14),
        processed_days=_env_int("DATA_API_RETENTION_PROCESSED_DAYS", 30),
        exports_days=_env_int("DATA_API_RETENTION_EXPORTS_DAYS", 60),
        archive_days=_env_int("DATA_API_RETENTION_ARCHIVE_DAYS", 180),
    )


def _iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (p for p in root.rglob("*") if p.is_file())


def _is_older_than(path: Path, cutoff: datetime) -> bool:
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    return modified < cutoff


def _safe_archive_target(archive_root: Path, bucket: str, source: Path) -> Path:
    now = datetime.now()
    target_dir = archive_root / bucket / now.strftime("%Y") / now.strftime("%m")
    target_dir.mkdir(parents=True, exist_ok=True)

    candidate = target_dir / source.name
    if not candidate.exists():
        return candidate

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return target_dir / f"{source.stem}_{timestamp}{source.suffix}"


def _archive_or_delete(
    path: Path,
    bucket: str,
    archive_root: Path,
    do_archive: bool,
    dry_run: bool,
    result: RetentionResult,
) -> None:
    size = path.stat().st_size

    if do_archive:
        target = _safe_archive_target(archive_root, bucket, path)
        if not dry_run:
            shutil.move(str(path), str(target))
        result.archived += 1
        result.archived_bytes += size
        return

    if not dry_run:
        path.unlink(missing_ok=True)
    result.deleted += 1
    result.deleted_bytes += size


def _process_bucket(
    bucket_dir: Path,
    bucket_name: str,
    days: int,
    archive_root: Path,
    do_archive: bool,
    dry_run: bool,
    result: RetentionResult,
) -> None:
    cutoff = datetime.now() - timedelta(days=days)

    for path in _iter_files(bucket_dir):
        if _is_older_than(path, cutoff):
            _archive_or_delete(path, bucket_name, archive_root, do_archive, dry_run, result)


def _prune_archive(archive_root: Path, archive_days: int, dry_run: bool, result: RetentionResult) -> None:
    if not archive_root.exists():
        return

    cutoff = datetime.now() - timedelta(days=archive_days)
    for path in _iter_files(archive_root):
        if _is_older_than(path, cutoff):
            size = path.stat().st_size
            if not dry_run:
                path.unlink(missing_ok=True)
            result.pruned_archive += 1
            result.pruned_archive_bytes += size


def run_retention(
    data_root: Path,
    policy: RetentionPolicy,
    archive_root: Path,
    do_archive: bool,
    prune_archive: bool,
    dry_run: bool,
) -> RetentionResult:
    result = RetentionResult()

    _process_bucket(
        bucket_dir=data_root / "raw",
        bucket_name="raw",
        days=policy.raw_days,
        archive_root=archive_root,
        do_archive=do_archive,
        dry_run=dry_run,
        result=result,
    )
    _process_bucket(
        bucket_dir=data_root / "processed",
        bucket_name="processed",
        days=policy.processed_days,
        archive_root=archive_root,
        do_archive=do_archive,
        dry_run=dry_run,
        result=result,
    )
    _process_bucket(
        bucket_dir=data_root / "exports",
        bucket_name="exports",
        days=policy.exports_days,
        archive_root=archive_root,
        do_archive=do_archive,
        dry_run=dry_run,
        result=result,
    )

    if prune_archive:
        _prune_archive(archive_root=archive_root, archive_days=policy.archive_days, dry_run=dry_run, result=result)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run data retention and archival for Volt datasets.")
    parser.add_argument("--data-root", default=os.getenv("DATA_API_DATA_ROOT", "data_api/data"), help="Data root path.")
    parser.add_argument(
        "--archive-root",
        default=os.getenv("DATA_API_ARCHIVE_ROOT", ""),
        help="Archive root path. Defaults to <data-root>/archive when not set.",
    )
    parser.add_argument("--raw-days", type=int, default=_build_policy().raw_days, help="Retention days for raw files.")
    parser.add_argument(
        "--processed-days",
        type=int,
        default=_build_policy().processed_days,
        help="Retention days for processed files.",
    )
    parser.add_argument(
        "--exports-days",
        type=int,
        default=_build_policy().exports_days,
        help="Retention days for export files.",
    )
    parser.add_argument(
        "--archive-days",
        type=int,
        default=_build_policy().archive_days,
        help="Retention days for files already in archive.",
    )
    parser.add_argument(
        "--delete-only",
        action="store_true",
        help="Delete expired files directly instead of moving to archive.",
    )
    parser.add_argument(
        "--prune-archive",
        action="store_true",
        help="Also prune archive files older than --archive-days.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without changing files.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    data_root = Path(args.data_root)
    archive_root = Path(args.archive_root) if args.archive_root else data_root / "archive"

    policy = RetentionPolicy(
        raw_days=args.raw_days,
        processed_days=args.processed_days,
        exports_days=args.exports_days,
        archive_days=args.archive_days,
    )

    result = run_retention(
        data_root=data_root,
        policy=policy,
        archive_root=archive_root,
        do_archive=not args.delete_only,
        prune_archive=args.prune_archive,
        dry_run=args.dry_run,
    )

    summary = {
        "data_root": str(data_root),
        "archive_root": str(archive_root),
        "policy_days": {
            "raw": policy.raw_days,
            "processed": policy.processed_days,
            "exports": policy.exports_days,
            "archive": policy.archive_days,
        },
        "mode": {
            "archive": not args.delete_only,
            "prune_archive": args.prune_archive,
            "dry_run": args.dry_run,
        },
        "result": result.as_dict(),
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
