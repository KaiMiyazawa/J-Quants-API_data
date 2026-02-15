from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .checkpoints import CheckpointStore
from .config import load_settings
from .datasets import build_calendar_params, build_dataset_specs, build_weekly_ranges
from .jquants_rest import JQuantsRestClient
from .logging_setup import setup_logging
from .rate_limit import TokenBucketRateLimiter
from .storage import LakePaths, new_run_id, utc_now_iso, write_jsonl_gz, write_manifest

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - optional
    tqdm = None

log = logging.getLogger(__name__)


def _scope_for_range(date_from: str, date_to: str) -> str:
    return f"from={date_from}_to={date_to}"


def _dt_for_scope(scope: str) -> str:
    if scope.startswith("dt="):
        return scope.split("=", 1)[1]
    if scope.startswith("from="):
        return scope.split("from=", 1)[1].split("_to=", 1)[0]
    if scope == "all":
        return "all"
    return scope


def _fetch_with_pagination(
    cli: JQuantsRestClient,
    limiter: TokenBucketRateLimiter,
    lake: LakePaths,
    cps: CheckpointStore,
    dataset: str,
    endpoint: str,
    scope: str,
    params: Dict[str, Any],
) -> None:
    cp = cps.get(dataset, scope)
    dt = _dt_for_scope(scope)
    if cp and cp["status"] == "done":
        log.info("SKIP (done): %s %s", dataset, scope)
        return

    # If data already exists on disk, skip even without checkpoint (resume-safe).
    bronze_root = lake.root / "bronze" / f"dataset={dataset}" / f"dt={dt}"
    if bronze_root.exists():
        # Any existing run directory object is truthy, so we must check for actual page files.
        has_data = any(
            any(run_dir.glob("page=*.jsonl.gz"))
            for run_dir in bronze_root.glob("run_id=*/")
        )
        if has_data:
            log.info("SKIP (disk exists): %s %s", dataset, scope)
            cps.upsert(
                dataset,
                scope,
                "done",
                {"run_id": "existing", "note": "skipped due to existing files"},
                utc_now_iso(),
            )
            return

    run_id = cp["payload"].get("run_id") if cp else None
    if not run_id:
        run_id = new_run_id()

    page_index = int(cp["payload"].get("page_index", 0)) if cp else 0
    pagination_key = cp["payload"].get("pagination_key") if cp else None
    if pagination_key:
        params = dict(params)
        params["pagination_key"] = pagination_key

    out_dir = lake.bronze_dir(dataset, dt, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    cps.upsert(
        dataset,
        scope,
        "in_progress",
        {
            "run_id": run_id,
            "params": params,
            "pagination_key": pagination_key,
            "page_index": page_index,
        },
        utc_now_iso(),
    )

    total_rows = 0
    total_pages = 0

    def _iterate_pages():
        nonlocal total_rows, total_pages
        resume_offset = page_index
        for page_no, rows, next_key in cli.iter_pages(endpoint, params, rate_limiter=limiter):
            actual_page_no = resume_offset + page_no
            total_pages += 1
            out_file = out_dir / f"page={actual_page_no:06d}.jsonl.gz"
            row_count = write_jsonl_gz(rows, out_file)
            total_rows += row_count

            cps.upsert(
                dataset,
                scope,
                "in_progress",
                {
                    "run_id": run_id,
                    "params": params,
                    "pagination_key": next_key,
                    "page_index": actual_page_no,
                },
                utc_now_iso(),
            )

            if not next_key:
                break

    try:
        _iterate_pages()
    except RuntimeError as e:
        msg = str(e)
        if "subscription covers the following dates" in msg:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", msg)
            if m:
                min_date = m.group(1)
                if scope.startswith("dt="):
                    dt_val = _dt_for_scope(scope)
                    if dt_val < min_date:
                        log.warning(
                            "SKIP (out of subscription window): %s %s (min=%s)",
                            dataset,
                            scope,
                            min_date,
                        )
                        cps.upsert(
                            dataset,
                            scope,
                            "done",
                            {"run_id": run_id, "note": f"skipped before {min_date}"},
                            utc_now_iso(),
                        )
                        return
                if scope.startswith("from="):
                    date_from = params.get("from")
                    if date_from and date_from < min_date:
                        log.warning(
                            "Adjusting range from=%s -> %s for %s %s",
                            date_from,
                            min_date,
                            dataset,
                            scope,
                        )
                        params["from"] = min_date
                        _iterate_pages()
                        # continue to manifest creation below
                    else:
                        raise
            else:
                raise
        else:
            raise

    manifest = {
        "dataset": dataset,
        "endpoint": endpoint,
        "scope": scope,
        "dt": dt,
        "run_id": run_id,
        "params": params,
        "pages": total_pages,
        "row_count": total_rows,
        "created_at": utc_now_iso(),
    }
    write_manifest(out_dir / "manifest.json", manifest)
    cps.upsert(dataset, scope, "done", {"run_id": run_id, "pages": total_pages}, utc_now_iso())
    log.info("DONE: %s %s pages=%s rows=%s", dataset, scope, total_pages, total_rows)


def _fetch_calendar(cli: JQuantsRestClient, limiter: TokenBucketRateLimiter, date_from: str, date_to: str) -> List[str]:
    params = build_calendar_params(date_from, date_to)
    data = []
    while True:
        try:
            for _, rows, _ in cli.iter_pages("/markets/calendar", params, rate_limiter=limiter):
                data.extend(rows)
            break
        except RuntimeError as e:
            msg = str(e)
            if "subscription covers the following dates" in msg:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", msg)
                if m:
                    new_from = m.group(1)
                    if new_from != params.get("from"):
                        if new_from > str(params.get("to")):
                            log.warning(
                                "Requested range %s..%s is fully out of subscription window (min=%s).",
                                params.get("from"),
                                params.get("to"),
                                new_from,
                            )
                            return []
                        log.warning("Adjusting calendar from=%s -> %s based on subscription window.", params.get("from"), new_from)
                        params["from"] = new_from
                        continue
            raise

    if not data:
        return []

    # Try common date keys
    for key in ["Date", "date", "TradingDate", "trading_date"]:
        if key in data[0]:
            return sorted({str(item[key])[:10] for item in data})

    # Fallback: first key
    first_key = list(data[0].keys())[0]
    return sorted({str(item[first_key])[:10] for item in data})


def _parse_args() -> argparse.Namespace:
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

    return p.parse_args()


def cmd_backfill(args: argparse.Namespace) -> None:
    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()
    cps = CheckpointStore(st.checkpoint_db)

    cli = JQuantsRestClient(
        api_key=st.api_key,
        base_url=st.api_base_url,
        timeout_sec=st.http_timeout_sec,
        max_retry=st.max_retry,
        retry_base_sleep_sec=st.retry_base_sleep_sec,
    )
    limiter = TokenBucketRateLimiter(st.max_req_per_min)

    trading_days = _fetch_calendar(cli, limiter, args.from_date, args.to_date)
    if not trading_days:
        log.warning("No trading days in requested range: from=%s to=%s. Skip backfill.", args.from_date, args.to_date)
        return

    # Store calendar range as dataset
    _fetch_with_pagination(
        cli,
        limiter,
        lake,
        cps,
        dataset="mkt_calendar",
        endpoint="/markets/calendar",
        scope=_scope_for_range(args.from_date, args.to_date),
        params=build_calendar_params(args.from_date, args.to_date),
    )

    specs = build_dataset_specs()

    weekly_ranges = build_weekly_ranges(trading_days)

    day_iter = trading_days
    if tqdm is not None:
        day_iter = tqdm(trading_days, desc="backfill-days", ascii=True)

    for dt in day_iter:
        for spec in specs:
            if spec.mode != "daily":
                continue
            params = spec.param_builder(dt)
            scope = f"dt={dt}"
            _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, scope, params)

    # Weekly datasets
    for date_from, date_to in weekly_ranges:
        for spec in specs:
            if spec.mode != "weekly":
                continue
            params = {"from": date_from, "to": date_to}
            scope = _scope_for_range(date_from, date_to)
            _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, scope, params)

    # Event datasets
    for spec in specs:
        if spec.mode != "event":
            continue
        _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, "all", {})


def cmd_incremental(args: argparse.Namespace) -> None:
    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()
    cps = CheckpointStore(st.checkpoint_db)

    cli = JQuantsRestClient(
        api_key=st.api_key,
        base_url=st.api_base_url,
        timeout_sec=st.http_timeout_sec,
        max_retry=st.max_retry,
        retry_base_sleep_sec=st.retry_base_sleep_sec,
    )
    limiter = TokenBucketRateLimiter(st.max_req_per_min)

    dt = args.date
    specs = build_dataset_specs()

    for spec in specs:
        if spec.mode == "daily":
            params = spec.param_builder(dt)
            scope = f"dt={dt}"
            _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, scope, params)
        elif spec.mode == "daily_am":
            params = spec.param_builder(dt)
            scope = f"dt={dt}"
            _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, scope, params)

    # Weekly datasets: fetch week containing dt
    trading_days = _fetch_calendar(cli, limiter, dt, dt)
    if trading_days:
        weekly_ranges = build_weekly_ranges(trading_days)
        for date_from, date_to in weekly_ranges:
            for spec in specs:
                if spec.mode != "weekly":
                    continue
                params = {"from": date_from, "to": date_to}
                scope = _scope_for_range(date_from, date_to)
                _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, scope, params)

    # Event datasets
    for spec in specs:
        if spec.mode != "event":
            continue
        _fetch_with_pagination(cli, limiter, lake, cps, spec.name, spec.endpoint, "all", {})


def cmd_bulk_sync(args: argparse.Namespace) -> None:
    import requests

    st = load_settings()
    setup_logging(st.log_level)

    lake = LakePaths(st.data_lake_root)
    lake.ensure()

    cli = JQuantsRestClient(
        api_key=st.api_key,
        base_url=st.api_base_url,
        timeout_sec=st.http_timeout_sec,
        max_retry=st.max_retry,
        retry_base_sleep_sec=st.retry_base_sleep_sec,
    )
    limiter = TokenBucketRateLimiter(st.max_req_per_min)

    endpoints = [
        "/equities/bars/daily",
        "/fins/summary",
        "/indices/bars/daily/topix",
        "/markets/breakdown",
    ]

    bulk_dir = lake.root / "bulk_raw"
    bulk_dir.mkdir(parents=True, exist_ok=True)

    for ep in endpoints:
        limiter.acquire(1.0)
        data = cli.request_json("/bulk/list", {"endpoint": ep})
        files = data.get("data", [])
        if not files:
            log.warning("No bulk files for endpoint=%s", ep)
            continue

        for item in files:
            key = str(item.get("Key"))
            if not key:
                continue
            # Key already includes extension; avoid double .gz.gz
            out_path = bulk_dir / ep.strip("/").replace("/", "__") / key
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if out_path.exists():
                continue

            limiter.acquire(1.0)
            data = cli.request_json("/bulk/get", {"key": key})
            url = data.get("url")
            if not url:
                raise RuntimeError(f"bulk/get returned no url for key={key}")

            res = requests.get(url, timeout=st.http_timeout_sec)
            res.raise_for_status()
            out_path.write_bytes(res.content)
            log.info("Bulk saved: %s", out_path)


def main() -> None:
    args = _parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
