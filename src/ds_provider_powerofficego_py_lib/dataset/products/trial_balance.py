"""
**File:** ``trial_balance.py``
**Region:** ``ds_provider_powerofficego_py_lib/dataset/products/trial_balance``

TrialBalance product helpers.

PowerOffice ``GET /TrialBalance`` is point-in-time (``date`` query param). History
is built by repeating that call for each month-end from
``TrialBalanceFilter.DATE_FROM`` through ``TrialBalanceFilter.DATE_TO``
(default: today). Those keys are provider filters, not native PoGo query params.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pandas as pd
from ds_common_logger_py_lib import Logger
from ds_resource_plugin_py_lib.common.resource.dataset.errors import ReadError

from ...enums import DataProduct, TrialBalanceFilter
from ..utils import build_checkpoint, build_params, build_url, records_from_body

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ..powerofficego import PowerOfficeGoDataset

logger = Logger.get_logger(__name__, package=True)


def handles(*, data_product: str, filters: dict[str, Any] | None) -> bool:
    """True when this product should run the month-end history fetch."""
    return data_product == DataProduct.TRIAL_BALANCE and bool(filters and filters.get(TrialBalanceFilter.DATE_FROM))


def reject_if_misused(*, data_product: str, filters: dict[str, Any] | None) -> None:
    """Raise if TrialBalance history filters are set on another product."""
    if not filters or data_product == DataProduct.TRIAL_BALANCE:
        return
    for key in TrialBalanceFilter:
        if filters.get(key) is not None:
            raise ReadError(
                message=f"filters.{key} is only meaningful for {DataProduct.TRIAL_BALANCE}.",
                details={"data_product": data_product, key: filters.get(key)},
            )


def _parse_iso_date(raw: Any, key: TrialBalanceFilter, *, data_product: str) -> date:
    """Parse a non-empty filter value as an ISO date (``YYYY-MM-DD``)."""
    if not isinstance(raw, str):
        raise ReadError(
            message=f"filters.{key} must be an ISO date string (YYYY-MM-DD), got: {raw!r}",
            details={"data_product": data_product, key: raw},
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ReadError(
            message=f"filters.{key} must be an ISO date (YYYY-MM-DD), got: {raw!r}",
            details={"data_product": data_product, key: raw},
        ) from exc


def resolve_date_from(filters: dict[str, Any] | None, *, data_product: str) -> date:
    """Parse ``filters.date_from`` as an ISO date (``YYYY-MM-DD``); required for history reads."""
    raw = (filters or {}).get(TrialBalanceFilter.DATE_FROM)
    if raw is None:
        raise ReadError(
            message=f"filters.{TrialBalanceFilter.DATE_FROM} is required for {DataProduct.TRIAL_BALANCE} history reads.",
            details={"data_product": data_product},
        )
    return _parse_iso_date(raw, TrialBalanceFilter.DATE_FROM, data_product=data_product)


def resolve_date_to(filters: dict[str, Any] | None, *, data_product: str, default: date) -> date:
    """Parse optional ``filters.date_to``; default to ``default`` (typically today)."""
    raw = (filters or {}).get(TrialBalanceFilter.DATE_TO)
    if raw is None:
        return default
    return _parse_iso_date(raw, TrialBalanceFilter.DATE_TO, data_product=data_product)


def month_end_as_of_dates(*, date_from: date, date_to: date) -> Iterator[date]:
    """Yield month-end as-of dates from ``date_from`` through ``date_to`` (inclusive)."""
    if date_from > date_to:
        return
    cursor = date_from.replace(day=1)
    while cursor <= date_to:
        next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        yield min(month_end, date_to)
        cursor = next_month


def fetch_history(dataset: PowerOfficeGoDataset[Any, Any], session: Any) -> None:
    """Fetch TrialBalance once per month-end as-of date; stamp each row with ``date``."""
    today = datetime.now(tz=timezone.utc).date()
    filters = dataset.settings.read.filters
    data_product = dataset.settings.data_product
    date_from = resolve_date_from(filters, data_product=data_product)
    date_to = resolve_date_to(filters, data_product=data_product, default=today)
    if date_from > date_to:
        raise ReadError(
            message=(f"filters.{TrialBalanceFilter.DATE_FROM} must be on or before filters.{TrialBalanceFilter.DATE_TO}."),
            details={
                "data_product": data_product,
                TrialBalanceFilter.DATE_FROM: date_from.isoformat(),
                TrialBalanceFilter.DATE_TO: date_to.isoformat(),
            },
        )

    as_of_dates = list(month_end_as_of_dates(date_from=date_from, date_to=date_to))
    logger.info(
        "TrialBalance history from %s to %s (%s as-of dates)",
        date_from.isoformat(),
        date_to.isoformat(),
        len(as_of_dates),
    )

    all_records: list[dict[str, Any]] = []
    last_successful_page = 0
    ls_settings = dataset.linked_service.settings
    url = build_url(
        host=ls_settings.host,
        api_version=ls_settings.api_version,
        data_product=data_product,
    )
    current_as_of = as_of_dates[0].isoformat() if as_of_dates else date_to.isoformat()
    page = 1

    try:
        for as_of in as_of_dates:
            current_as_of = as_of.isoformat()
            page = 1
            while True:
                params = build_params(dataset.settings, page, last_modified_date=None, as_of=current_as_of)
                logger.debug("Making API request to %s with params: %s", url, params)
                response = session.get(url=url, params=params)
                if response.status_code == 204:
                    logger.info("Received 204 No Content for as-of %s. Next date.", current_as_of)
                    break
                page_records = records_from_body(response.json())
                for record in page_records:
                    stamped = dict(record)
                    stamped["date"] = current_as_of
                    all_records.append(stamped)
                logger.info(
                    "Fetched TrialBalance as-of %s page %s with %s records.",
                    current_as_of,
                    page,
                    len(page_records),
                )
                last_successful_page = page

                pagination_header = response.headers.get("X-Pagination")
                if pagination_header:
                    pagination = json.loads(pagination_header)
                    if not pagination.get("nextPageLink"):
                        break
                else:
                    break
                page += 1
    except ReadError:
        raise
    except Exception as exc:
        logger.error("Error occurred while fetching TrialBalance history: %s", exc)
        dataset.checkpoint = build_checkpoint(last_successful_page, last_modified_date=None)
        raise ReadError(
            message=f"Error occurred while fetching TrialBalance history: {exc}",
            details={
                "last_successful_page": last_successful_page,
                "failed_page": page,
                "as_of": current_as_of,
                "data_product": data_product,
                "settings": dataset.settings,
            },
        ) from exc

    dataset.output = pd.DataFrame(all_records)
    dataset.checkpoint = build_checkpoint(last_successful_page, last_modified_date=None)
