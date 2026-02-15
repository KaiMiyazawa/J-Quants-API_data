from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable, List, Optional, Tuple


def _compact(dt: str) -> str:
    return dt.replace("-", "")


def _week_key(d: date) -> Tuple[int, int]:
    iso = d.isocalendar()
    return iso.year, iso.week


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    endpoint: str
    mode: str  # daily | weekly | range | event | daily_am
    param_builder: Callable[[str], dict[str, Any]]


def build_dataset_specs() -> List[DatasetSpec]:
    return [
        # Free
        DatasetSpec(
            name="eq_master",
            endpoint="/equities/master",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="eq_bars_daily",
            endpoint="/equities/bars/daily",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="fin_summary",
            endpoint="/fins/summary",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="eq_earnings_cal",
            endpoint="/equities/earnings-calendar",
            mode="event",
            param_builder=lambda dt: {},
        ),
        DatasetSpec(
            name="mkt_calendar",
            endpoint="/markets/calendar",
            mode="range",
            param_builder=lambda dt: {},
        ),
        # Light
        DatasetSpec(
            name="eq_investor_types",
            endpoint="/equities/investor-types",
            mode="weekly",
            param_builder=lambda dt: {},
        ),
        DatasetSpec(
            name="idx_bars_daily_topix",
            endpoint="/indices/bars/daily/topix",
            mode="daily",
            param_builder=lambda dt: {"from": dt, "to": dt},
        ),
        # Standard
        DatasetSpec(
            name="idx_bars_daily",
            endpoint="/indices/bars/daily",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="drv_bars_daily_opt_225",
            endpoint="/derivatives/bars/daily/options/225",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="mkt_margin_interest",
            endpoint="/markets/margin-interest",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="mkt_short_ratio",
            endpoint="/markets/short-ratio",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="mkt_short_sale_report",
            endpoint="/markets/short-sale-report",
            mode="daily",
            param_builder=lambda dt: {"disc_date": _compact(dt)},
        ),
        DatasetSpec(
            name="mkt_margin_alert",
            endpoint="/markets/margin-alert",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        # Premium
        DatasetSpec(
            name="mkt_breakdown",
            endpoint="/markets/breakdown",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="eq_bars_daily_am",
            endpoint="/equities/bars/daily/am",
            mode="daily_am",
            param_builder=lambda dt: {},
        ),
        DatasetSpec(
            name="fin_dividend",
            endpoint="/fins/dividend",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="fin_details",
            endpoint="/fins/details",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="drv_bars_daily_fut",
            endpoint="/derivatives/bars/daily/futures",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
        DatasetSpec(
            name="drv_bars_daily_opt",
            endpoint="/derivatives/bars/daily/options",
            mode="daily",
            param_builder=lambda dt: {"date": _compact(dt)},
        ),
    ]


def build_calendar_params(date_from: str, date_to: str) -> dict[str, Any]:
    return {"from": date_from, "to": date_to}


def build_weekly_ranges(trading_days: List[str]) -> List[Tuple[str, str]]:
    if not trading_days:
        return []

    from datetime import datetime

    grouped: dict[Tuple[int, int], List[str]] = {}
    for dt_str in trading_days:
        d = datetime.strptime(dt_str, "%Y-%m-%d").date()
        grouped.setdefault(_week_key(d), []).append(dt_str)

    ranges: List[Tuple[str, str]] = []
    for key in sorted(grouped.keys()):
        days = sorted(grouped[key])
        ranges.append((days[0], days[-1]))
    return ranges
