以下に、**`jquants-api-client`（`J-Quants/jquants-api-client-python`）前提**で、あなたの「Premium 全データをデータレイク化（バックフィル＋増分）」を実行できる **リポジトリ一式（雛形コード）**を提示します。
このままファイルを作成していけば動くように、**venv / .env / requirements.txt / CLI / checkpoint(SQLite) / Bronze(jsonl.gz) / Silver(parquet)** を含めています。

根拠（公式クライアントが `ClientV2` とV2ラッパー群を提供すること、設定読み込み順、range系の注意など）として、`jquants-api-client-python` README を参照しています。 ([GitHub][1])

---

## 1) ディレクトリ構成（提案）

```text
jquants-lake/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
└── src/
    ├── main.py
    ├── config.py
    ├── logging_setup.py
    ├── rate_limit.py
    ├── checkpoints.py
    ├── storage.py
    ├── jquants_client.py
    ├── datasets.py
    └── normalize.py
```

---

## 2) `requirements.txt`

```txt
jquants-api-client>=1.9.0
python-dotenv>=1.0.0
tenacity>=8.2.3
pandas>=2.0.0
pyarrow>=14.0.0
orjson>=3.9.0
requests>=2.31.0
tqdm>=4.66.0
SQLAlchemy>=2.0.0
```

---

## 3) `.env.example`

```env
# J-Quants (V2)
JQUANTS_API_KEY=xxxxxxxxxxxxxxxxxxxx

# Data Lake root
DATA_LAKE_ROOT=./data_lake

# Throttling (Premium: 500 req/min → safety: 480)
MAX_REQ_PER_MIN=480
HTTP_TIMEOUT_SEC=60

# Retry
MAX_RETRY=8
RETRY_BASE_SLEEP_SEC=2

# Checkpoint DB
CHECKPOINT_DB=./run/checkpoints.sqlite

# Logging
LOG_LEVEL=INFO
```

---

## 4) `.gitignore`

```gitignore
.venv/
__pycache__/
*.pyc
.env
data_lake/
run/
*.parquet
*.gz
*.sqlite
```

---

## 5) `README.md`

````md
# J-Quants Premium Data Lake (V2 / jquants-api-client)

本リポジトリは、J-Quants API Premium で取得可能なデータセットを「バックフィル + 増分更新」し、
データレイク（Bronze/Silver）として保存するための実行基盤です。

公式Pythonクライアント `jquants-api-client` の `ClientV2` を使用します。 :contentReference[oaicite:1]{index=1}

## 0. 前提
- `.env` に `JQUANTS_API_KEY` を設定してください。
- Premium のレート制御は上限500 req/minのため、デフォルトは480 req/minです（安全側）。

## 1. セットアップ（venv）
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# .env を編集（JQUANTS_API_KEY など）
````

## 2. 実行例

### 2.1 バックフィル（期間指定）

```bash
python -m src.main backfill --from 2008-05-07 --to 2026-01-24
```

### 2.2 増分（単日）

```bash
python -m src.main incremental --date 2026-01-24
```

### 2.3 Bulk同期（可能なデータはCSVバルクで回収）

```bash
python -m src.main bulk-sync
```

### 2.4 Silver生成（Bronze → Parquet）

```bash
python -m src.main normalize --dataset eq_bars_daily --date 2026-01-24
```

## 3. 保存先（DATA_LAKE_ROOT）

* Bronze（Raw）: jsonl.gz（1取得単位=1ファイル）
* Silver（Normalized）: parquet（dtパーティション）

例:
DATA_LAKE_ROOT/
bronze/dataset=eq_bars_daily/dt=2026-01-24/run_id=.../part-0000.jsonl.gz
silver/dataset=eq_bars_daily/dt=2026-01-24/part-0000.parquet
metadata/checkpoints.sqlite

## 4. 重要な注意

* `jquants-api-client` には `*_range` 系ユーティリティがあり、内部で複数リクエストを発行するため、
  範囲が広い/連続実行ではレートリミット到達の可能性がある旨が README に記載されています。 ([GitHub][1])
  本実装では、原則として自前のchunking + レート制御で取得します。

````

---

## 6) `src/config.py`

```python
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

    return Settings(
        api_key=api_key,
        data_lake_root=data_lake_root,
        max_req_per_min=max_req_per_min,
        http_timeout_sec=http_timeout_sec,
        max_retry=max_retry,
        retry_base_sleep_sec=retry_base_sleep_sec,
        checkpoint_db=checkpoint_db,
        log_level=log_level,
    )
````

---

## 7) `src/logging_setup.py`

```python
import logging
import sys


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        stream=sys.stdout,
    )
```

---

## 8) `src/rate_limit.py`

```python
from __future__ import annotations

import threading
import time


class TokenBucketRateLimiter:
    """
    1分窓の簡易トークンバケット。
    Premium上限(500/min)に対して、安全側に max_per_min を設定して使用。
    """

    def __init__(self, max_per_min: int) -> None:
        self.capacity = max_per_min
        self.tokens = float(max_per_min)
        self.refill_rate_per_sec = max_per_min / 60.0
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.last = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # 足りない分だけ待つ
                needed = tokens - self.tokens
                wait = needed / self.refill_rate_per_sec if self.refill_rate_per_sec > 0 else 1.0

            time.sleep(max(wait, 0.05))
```

---

## 9) `src/checkpoints.py`（SQLite）

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    create_engine,
    select,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True)
    dataset = Column(String(128), nullable=False)
    scope = Column(String(128), nullable=False)  # e.g., "dt=2026-01-24"
    status = Column(String(32), nullable=False)  # "done" | "in_progress" | "failed"
    payload_json = Column(Text, nullable=False, default="{}")  # extra info (e.g., pagination)
    updated_at = Column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("dataset", "scope", name="uq_dataset_scope"),)


@dataclass
class CheckpointStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get(self, dataset: str, scope: str) -> Optional[dict[str, Any]]:
        with self.Session() as s:
            row = s.execute(
                select(Checkpoint).where(Checkpoint.dataset == dataset, Checkpoint.scope == scope)
            ).scalar_one_or_none()
            if not row:
                return None
            return {"status": row.status, "payload": json.loads(row.payload_json)}

    def upsert(self, dataset: str, scope: str, status: str, payload: dict[str, Any], updated_at: str) -> None:
        with self.Session() as s:
            row = s.execute(
                select(Checkpoint).where(Checkpoint.dataset == dataset, Checkpoint.scope == scope)
            ).scalar_one_or_none()
            if row:
                row.status = status
                row.payload_json = json.dumps(payload, ensure_ascii=False)
                row.updated_at = updated_at
            else:
                row = Checkpoint(
                    dataset=dataset,
                    scope=scope,
                    status=status,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                    updated_at=updated_at,
                )
                s.add(row)
            s.commit()
```

---

## 10) `src/storage.py`（Bronze/SilverのI/O）

```python
from __future__ import annotations

import gzip
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


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


def df_to_jsonl_gz(df: pd.DataFrame, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = df.to_dict(orient="records")
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False))
            f.write("\n")
    return len(rows)


def jsonl_gz_to_parquet(in_path: Path, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(in_path, "rt", encoding="utf-8") as f:
        df = pd.read_json(f, lines=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path)
    return len(df)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
```

---

## 11) `src/jquants_client.py`（`ClientV2` ラッパー＋シグネチャ適応）

公式READMEより `ClientV2(api_key=...)` が使用可能で、環境変数 `JQUANTS_API_KEY` でも動くことが示されています。 ([GitHub][1])

```python
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable

import jquantsapi
import pandas as pd


log = logging.getLogger(__name__)


@dataclass
class JQuantsV2:
    api_key: str

    def __post_init__(self) -> None:
        # 公式READMEにある ClientV2 を使用 :contentReference[oaicite:4]{index=4}
        self.cli = jquantsapi.ClientV2(api_key=self.api_key)

    def _adapt_params(self, fn: Callable[..., Any], params: dict[str, Any]) -> dict[str, Any]:
        """
        ライブラリ側の引数名差異（from/to が from_ / to_ になる等）を吸収する。
        """
        sig = inspect.signature(fn)
        allowed = set(sig.parameters.keys())

        adapted = dict(params)

        # Python予約語対策: from / to
        if "from" in adapted and "from_" in allowed and "from" not in allowed:
            adapted["from_"] = adapted.pop("from")
        if "to" in adapted and "to_" in allowed and "to" not in allowed:
            adapted["to_"] = adapted.pop("to")

        # ありがちな別名（安全のため）
        if "start_dt" in adapted and "start_dt" not in allowed and "from_" in allowed:
            adapted["from_"] = adapted.pop("start_dt")
        if "end_dt" in adapted and "end_dt" not in allowed and "to_" in allowed:
            adapted["to_"] = adapted.pop("end_dt")

        # 不要キーを落とす
        filtered = {k: v for k, v in adapted.items() if k in allowed and v is not None}
        return filtered

    def call_df(self, method: str, **params: Any) -> pd.DataFrame:
        fn = getattr(self.cli, method, None)
        if fn is None:
            raise AttributeError(f"ClientV2 has no method: {method}")

        call_params = self._adapt_params(fn, params)
        log.debug("Calling %s(%s)", method, call_params)

        out = fn(**call_params)

        # 多くのラッパーは DataFrame を返す前提（README例） :contentReference[oaicite:5]{index=5}
        if isinstance(out, pd.DataFrame):
            return out

        # 念のため：dict/listなどの場合の変換
        if isinstance(out, list):
            return pd.DataFrame(out)
        if isinstance(out, dict) and "data" in out:
            return pd.DataFrame(out["data"])
        return pd.DataFrame(out)
```

---

## 12) `src/datasets.py`（対象データセット定義＋取得戦略）

ここでは「Premiumで取れるものを漏れなく」を **公式READMEのラッパー群**を基準に定義します。 ([GitHub][1])
（将来 README が増えたらここに追加）

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd

from .jquants_client import JQuantsV2


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    client_method: str
    # dt単位で回せるものは dt を渡す。範囲/週次などは params 側で制御する。
    param_builder: Callable[[str], dict[str, Any]]


def _date_to_compact(dt: str) -> str:
    # "YYYY-MM-DD" -> "YYYYMMDD"
    return dt.replace("-", "")


def build_dataset_specs() -> list[DatasetSpec]:
    """
    取得対象（最低限）:
      - Free/Light/Standard/Premium で README に列挙されたもの :contentReference[oaicite:7]{index=7}
    ここでは「日次で安全に回せる」形の param_builder を用意する。
    """
    return [
        # Equities
        DatasetSpec(
            name="eq_master",
            client_method="get_eq_master",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},  # date-only snapshot
        ),
        DatasetSpec(
            name="eq_bars_daily",
            client_method="get_eq_bars_daily",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},  # date-only for all codes
        ),
        DatasetSpec(
            name="eq_bars_daily_am",
            client_method="get_eq_bars_daily_am",
            param_builder=lambda dt: {},  # spec上は当日中心。dtは保存パーティションに使う
        ),
        DatasetSpec(
            name="eq_earnings_cal",
            client_method="get_eq_earnings_cal",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="eq_investor_types",
            client_method="get_eq_investor_types",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},  # 実装上はAPI仕様で from/to の場合も
        ),
        # Markets
        DatasetSpec(
            name="mkt_calendar",
            client_method="get_mkt_calendar",
            param_builder=lambda dt: {"from": dt, "to": dt},
        ),
        DatasetSpec(
            name="mkt_breakdown",
            client_method="get_mkt_breakdown",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="mkt_short_ratio",
            client_method="get_mkt_short_ratio",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="mkt_short_sale_report",
            client_method="get_mkt_short_sale_report",
            param_builder=lambda dt: {"disc_date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="mkt_margin_interest",
            client_method="get_mkt_margin_interest",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="mkt_margin_alert",
            client_method="get_mkt_margin_alert",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        # Indices
        DatasetSpec(
            name="idx_bars_daily",
            client_method="get_idx_bars_daily",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="idx_bars_daily_topix",
            client_method="get_idx_bars_daily_topix",
            param_builder=lambda dt: {"from": dt, "to": dt},
        ),
        # Derivatives
        DatasetSpec(
            name="drv_bars_daily_fut",
            client_method="get_drv_bars_daily_fut",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="drv_bars_daily_opt",
            client_method="get_drv_bars_daily_opt",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="drv_bars_daily_opt_225",
            client_method="get_drv_bars_daily_opt_225",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        # Financials
        DatasetSpec(
            name="fin_summary",
            client_method="get_fin_summary",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="fin_details",
            client_method="get_fin_details",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
        DatasetSpec(
            name="fin_dividend",
            client_method="get_fin_dividend",
            param_builder=lambda dt: {"date": _date_to_compact(dt)},
        ),
    ]


def calendar_days(cli: JQuantsV2, date_from: str, date_to: str) -> list[str]:
    """
    営業日列挙: 可能なら get_mkt_calendar を使う。
    返り値は "YYYY-MM-DD" の list。
    """
    df = cli.call_df("get_mkt_calendar", **{"from": date_from, "to": date_to})
    # 仕様/列名が変動し得るため、よくある列名を探索
    for col in ["Date", "date", "TradingDate", "trading_date"]:
        if col in df.columns:
            out = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d").tolist()
            return sorted(set(out))
    # fallback: dfの先頭列
    if len(df.columns) >= 1:
        out = pd.to_datetime(df[df.columns[0]]).dt.strftime("%Y-%m-%d").tolist()
        return sorted(set(out))
    raise RuntimeError("Could not parse calendar response into dates.")
```

---

## 13) `src/normalize.py`（Bronze→Silver）

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .storage import LakePaths, jsonl_gz_to_parquet


def normalize_one(lake: LakePaths, dataset: str, dt: str, bronze_file: Path) -> Path:
    """
    Bronze(jsonl.gz) → Silver(parquet)
    """
    out_dir = lake.silver_dir(dataset, dt)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / bronze_file.name.replace(".jsonl.gz", ".parquet")
    jsonl_gz_to_parquet(bronze_file, out_path)
    return out_path
```

---

## 14) `src/main.py`（CLI：backfill/incremental/bulk-sync/normalize）

```python
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from .config import load_settings
from .logging_setup import setup_logging
from .rate_limit import TokenBucketRateLimiter
from .checkpoints import CheckpointStore
from .storage import LakePaths, new_run_id, df_to_jsonl_gz, write_manifest, utc_now_iso
from .jquants_client import JQuantsV2
from .datasets import build_dataset_specs, calendar_days
from .normalize import normalize_one

log = logging.getLogger(__name__)


def _retryable():
    # 429等はライブラリ側例外の型が固定でないため、ここでは例外全般をリトライ対象にし、
    # “非リトライ（キー不備等）”は運用で見える化して止める設計にする。
    return retry(
        stop=stop_after_attempt(8),
        wait=wait_exponential_jitter(initial=2, max=120),
        reraise=True,
    )


def fetch_and_store_one(
    cli: JQuantsV2,
    limiter: TokenBucketRateLimiter,
    lake: LakePaths,
    cps: CheckpointStore,
    dataset: str,
    method: str,
    dt: str,
    params: dict[str, Any],
) -> Path:
    scope = f"dt={dt}"
    cp = cps.get(dataset, scope)
    if cp and cp["status"] == "done":
        log.info("SKIP (done): %s %s", dataset, scope)
        return Path()

    run_id = new_run_id()
    out_dir = lake.bronze_dir(dataset, dt, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    cps.upsert(dataset, scope, "in_progress", {"run_id": run_id, "params": params}, utc_now_iso())

    @_retryable()
    def _call():
        limiter.acquire(1.0)
        return cli.call_df(method, **params)

    df = _call()

    out_file = out_dir / "part-0000.jsonl.gz"
    row_count = df_to_jsonl_gz(df, out_file)

    manifest = {
        "dataset": dataset,
        "client_method": method,
        "dt": dt,
        "run_id": run_id,
        "params": params,
        "row_count": row_count,
        "created_at": utc_now_iso(),
    }
    write_manifest(out_dir / "manifest.json", manifest)

    cps.upsert(dataset, scope, "done", {"run_id": run_id, "row_count": row_count}, utc_now_iso())
    log.info("DONE: %s %s rows=%s file=%s", dataset, scope, row_count, out_file)
    return out_file


def cmd_backfill(args: argparse.Namespace) -> None:
    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()
    cps = CheckpointStore(st.checkpoint_db)

    cli = JQuantsV2(st.api_key)
    limiter = TokenBucketRateLimiter(st.max_req_per_min)

    # 営業日ベースで回す（APIカレンダー優先）
    days = calendar_days(cli, args.from_date, args.to_date)
    specs = build_dataset_specs()

    for dt in days:
        for spec in specs:
            params = spec.param_builder(dt)
            # am系のように「当日中心」でも dtパーティションとして保存はする
            fetch_and_store_one(cli, limiter, lake, cps, spec.name, spec.client_method, dt, params)


def cmd_incremental(args: argparse.Namespace) -> None:
    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()
    cps = CheckpointStore(st.checkpoint_db)

    cli = JQuantsV2(st.api_key)
    limiter = TokenBucketRateLimiter(st.max_req_per_min)

    dt = args.date
    specs = build_dataset_specs()

    for spec in specs:
        params = spec.param_builder(dt)
        fetch_and_store_one(cli, limiter, lake, cps, spec.name, spec.client_method, dt, params)


def cmd_normalize(args: argparse.Namespace) -> None:
    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()

    # Bronzeファイル探索（単純に最新 run_id を選ぶ、などは運用拡張）
    bronze_root = lake.root / "bronze" / f"dataset={args.dataset}" / f"dt={args.date}"
    if not bronze_root.exists():
        raise RuntimeError(f"No bronze dir found: {bronze_root}")

    # すべての run_id 配下を対象（まずは愚直でOK）
    for run_dir in sorted(bronze_root.glob("run_id=*/")):
        for gz in run_dir.glob("*.jsonl.gz"):
            out = normalize_one(lake, args.dataset, args.date, gz)
            log.info("Normalized: %s -> %s", gz, out)


def cmd_bulk_sync(args: argparse.Namespace) -> None:
    """
    Bulk API は ClientV2 の get_bulk_list / get_bulk を使用して同期する。
    ただし、get_bulk が bytes を返すか、ファイルDLまで行うかはバージョン差があり得るため、
    返り値の型に応じて保存処理を分岐する。
    """
    import gzip
    import requests

    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()

    cli = JQuantsV2(st.api_key)
    limiter = TokenBucketRateLimiter(st.max_req_per_min)

    # どのendpointのバルクを回すかは運用で拡張（まずは代表例）
    endpoints = [
        "/equities/bars/daily",
        "/fins/summary",
        "/markets/breakdown",
        "/indices/bars/daily",
    ]

    bulk_dir = lake.root / "bulk_raw"
    bulk_dir.mkdir(parents=True, exist_ok=True)

    for ep in endpoints:
        limiter.acquire(1.0)
        df_list = cli.call_df("get_bulk_list", endpoint=ep)
        if df_list.empty:
            log.warning("No bulk files for endpoint=%s", ep)
            continue

        # 列名は Key/LastModified/Size を想定（V2 bulk/list）だが、念のため先頭列名を fallback
        key_col = "Key" if "Key" in df_list.columns else df_list.columns[0]
        lm_col = "LastModified" if "LastModified" in df_list.columns else None
        sz_col = "Size" if "Size" in df_list.columns else None

        for _, row in df_list.iterrows():
            key = str(row[key_col])
            out_path = bulk_dir / ep.strip("/").replace("/", "__") / f"{key}.gz"
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if out_path.exists():
                continue

            limiter.acquire(1.0)
            blob = cli.cli.get_bulk(key=key)  # 直接呼ぶ（型分岐のため）

            # 1) 既に bytes を返す（DL済み）の場合
            if isinstance(blob, (bytes, bytearray)):
                out_path.write_bytes(bytes(blob))
                log.info("Bulk saved (bytes): %s", out_path)
                continue

            # 2) URL を返す場合（/bulk/get の url 相当）→ requests でDL
            if isinstance(blob, str) and blob.startswith("http"):
                r = requests.get(blob, timeout=st.http_timeout_sec)
                r.raise_for_status()
                out_path.write_bytes(r.content)
                log.info("Bulk saved (url): %s", out_path)
                continue

            # 3) DataFrame 等になった場合は保存形式を変える（保険）
            try:
                import pandas as pd

                if isinstance(blob, pd.DataFrame):
                    # gzでjsonlとして保存
                    out_path = out_path.with_suffix(".jsonl.gz")
                    from .storage import df_to_jsonl_gz

                    df_to_jsonl_gz(blob, out_path)
                    log.info("Bulk saved (df as jsonl.gz): %s", out_path)
                    continue
            except Exception:
                pass

            raise RuntimeError(f"Unexpected bulk response type: {type(blob)} key={key}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jquants-lake")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_bf = sub.add_parser("backfill", help="Backfill by trading days")
    p_bf.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-DD")
    p_bf.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-DD")
    p_bf.set_defaults(func=cmd_backfill)

    p_inc = sub.add_parser("incremental", help="Incremental (single day)")
    p_inc.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_inc.set_defaults(func=cmd_incremental)

    p_bulk = sub.add_parser("bulk-sync", help="Sync bulk files (CSV/GZ)")
    p_bulk.set_defaults(func=cmd_bulk_sync)

    p_norm = sub.add_parser("normalize", help="Bronze -> Silver for a dataset/day")
    p_norm.add_argument("--dataset", required=True)
    p_norm.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_norm.set_defaults(func=cmd_normalize)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

---

# 15) 実装上の重要メモ（あなたの要件に合わせた運用設計）

* **「全通りのリクエスト」**を「パラメータ直積」でやると、Premiumの **500 req/min** 制限に対して破綻しやすいです。
  そのため上の雛形は、**まずは“日付単位（date-only）で全銘柄”**に寄せています（クライアントが `get_eq_bars_daily(date=...)` のようなラッパーを提供している前提）。公式READMEにもV2のラッパー群が列挙されています。 ([GitHub][1])
* `*_range` は便利ですが、READMEに「（範囲に対して）並列で多数リクエストを発行し得てレートリミット到達の恐れ」が示唆されています（少なくとも“注意”が書かれています）。そのため本雛形では **原則rangeを使わない**方針にしています。 ([GitHub][1])

---

## 次にやると良い拡張（優先度順）

1. **DatasetSpec の param_builder を仕様に合わせて精密化**

   * 例：投資部門別は date だけでなく from/to（週次）で回す方が自然な場合がある
2. **Bulk 同期の endpoint 一覧を Premium 全対象に増やす**
3. **“改定あり”データの append-only とキー設計（PublishedDate 等）**
4. **Silver 生成時のスキーマ固定（列型・キー列）＋ Parquet最適化**
5. **欠損検知（期待営業日×データセットの組合せが揃っているか）**

---

必要なら、次の返信で **「Premiumで取得できる全データセット（クライアントREADMEの全ラッパー）」を 100% カバー**するように `datasets.py` を拡張し、各データセットごとに「バックフィル粒度（daily/weekly/event）」と「推奨パラメータ窓（from/to）」を具体化した版を出します。

[1]: https://github.com/J-Quants/jquants-api-client-python "GitHub - J-Quants/jquants-api-client-python"

