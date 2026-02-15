from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    data_lake_root: Path
    max_req_per_min: int
    http_timeout_sec: int
    max_retry: int
    retry_base_sleep_sec: int
    checkpoint_db: Path
    log_level: str
    api_base_url: str


def load_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("JQUANTS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("JQUANTS_API_KEY is missing. Set it in .env")

    data_lake_root = Path(os.getenv("DATA_LAKE_ROOT", "./data_lake")).resolve()

    max_req_per_min = int(os.getenv("MAX_REQ_PER_MIN", "480"))
    http_timeout_sec = int(os.getenv("HTTP_TIMEOUT_SEC", "60"))
    max_retry = int(os.getenv("MAX_RETRY", "8"))
    retry_base_sleep_sec = int(os.getenv("RETRY_BASE_SLEEP_SEC", "2"))
    checkpoint_db = Path(os.getenv("CHECKPOINT_DB", "./run/checkpoints.sqlite")).resolve()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    api_base_url = os.getenv("JQUANTS_API_BASE_URL", "https://api.jquants.com/v2").strip()

    return Settings(
        api_key=api_key,
        data_lake_root=data_lake_root,
        max_req_per_min=max_req_per_min,
        http_timeout_sec=http_timeout_sec,
        max_retry=max_retry,
        retry_base_sleep_sec=retry_base_sleep_sec,
        checkpoint_db=checkpoint_db,
        log_level=log_level,
        api_base_url=api_base_url,
    )
