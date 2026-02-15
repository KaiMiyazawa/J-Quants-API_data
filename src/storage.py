from __future__ import annotations

import gzip
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    import orjson
except Exception:  # pragma: no cover - optional
    orjson = None


@dataclass(frozen=True)
class LakePaths:
    root: Path

    def bronze_dir(self, dataset: str, dt: str, run_id: str) -> Path:
        return self.root / "bronze" / f"dataset={dataset}" / f"dt={dt}" / f"run_id={run_id}"

    def silver_dir(self, dataset: str, dt: str) -> Path:
        return self.root / "silver" / f"dataset={dataset}" / f"dt={dt}"

    def metadata_dir(self) -> Path:
        return self.root / "metadata"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "bronze").mkdir(parents=True, exist_ok=True)
        (self.root / "silver").mkdir(parents=True, exist_ok=True)
        self.metadata_dir().mkdir(parents=True, exist_ok=True)


def new_run_id() -> str:
    return uuid.uuid4().hex


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _dumps(obj: Any) -> str:
    if orjson is not None:
        return orjson.dumps(obj).decode("utf-8")
    return json.dumps(obj, ensure_ascii=False)


def write_jsonl_gz(rows: Iterable[dict[str, Any]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(_dumps(row))
            f.write("\n")
            count += 1
    return count


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
