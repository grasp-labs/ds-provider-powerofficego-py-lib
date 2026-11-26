"""
**File:** ``utils.py``
**Region:** ``ds_provider_powerofficego_py_lib/dataset/utils``

Shared helpers for PowerOfficeGo dataset reads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ds_common_logger_py_lib import Logger

from ..endpoint_info import EndpointInfo
from ..enums import DataProduct, TrialBalanceFilter
from ..errors import InvalidIncrementalWatermarkException, UnsupportedIncrementalKindException

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = Logger.get_logger(__name__, package=True)

# Provider-only filter keys (not forwarded as PowerOffice query params).
_PROVIDER_FILTER_KEYS = frozenset(TrialBalanceFilter)


def records_from_body(body: Any) -> list[dict[str, Any]]:
    """Normalize a PowerOffice list or ``{data|value|values: [...]}`` payload to row dicts."""
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    if isinstance(body, dict):
        for key in ("data", "value", "values"):
            nested = body.get(key)
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]
    return []


def parse_iso8601_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp string to an aware UTC datetime for comparison.

    Handles up to 7 digits of fractional seconds by truncating to 6 (Python max).
    """
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    if "." in normalized:
        main, rest = normalized.split(".", 1)
        tz_pos = max(rest.find("+"), rest.find("-"))
        if tz_pos != -1:
            frac = rest[:tz_pos]
            tz = rest[tz_pos:]
        else:
            frac = rest
            tz = ""
        if len(frac) > 6:
            frac = frac[:6]
        normalized = f"{main}.{frac}{tz}"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise InvalidIncrementalWatermarkException(
            message=f"Unparseable time_field watermark: {value!r}",
            details={"value": value},
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def greatest_time_field_value(values: Sequence[Any]) -> Any:
    """Return the original value that sorts last by parsed UTC ``datetime``."""
    if not values:
        return None
    parsed: list[tuple[datetime, Any]] = []
    for raw in values:
        if not isinstance(raw, str):
            raise InvalidIncrementalWatermarkException(
                message=f"LastChangedDateTimeOffset watermarks must be strings, got {type(raw).__name__}",
                details={"value": raw},
            )
        parsed.append((parse_iso8601_timestamp(raw), raw))
    return max(parsed, key=lambda item: item[0])[1]


def greatest_incremental_value(values: Sequence[Any], *, kind: str) -> Any | None:
    """Return the greatest watermark among observed values for the given strategy."""
    if not values:
        return None
    if kind == "LastChangedDateTimeOffset":
        return greatest_time_field_value(values)
    raise UnsupportedIncrementalKindException(
        message=f"Unsupported incremental kind: {kind!r}",
        details={"kind": kind},
    )


def build_checkpoint(last_page: int | None, last_modified_date: str | None) -> dict[str, Any]:
    """Build a checkpoint dictionary for pagination / incremental state."""
    checkpoint = {
        "incremental": {"value": last_modified_date},
        "pagination": {"value": last_page},
    }
    logger.debug("Built checkpoint: %s", checkpoint)
    return checkpoint


def build_params(
    settings: Any,
    page: int,
    last_modified_date: str | None,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build PowerOfficeGo query params from dataset read settings.

    ``as_of`` sets TrialBalance ``date`` and overrides ``filters.date``.
    Product-only filter keys (e.g. ``date_from``) are not forwarded.

    ``LastChangedDateTimeOffset`` is auto-added to ``Fields`` for incremental
    products only — TrialBalance rejects that field (HTTP 400).
    """
    params: dict[str, Any] = {
        "PageNumber": page,
        "PageSize": settings.read.page_size,
    }
    data_product = getattr(settings, "data_product", None)
    append_incremental_field = data_product != DataProduct.TRIAL_BALANCE and as_of is None

    if settings.read.fields:
        fields = ",".join(settings.read.fields)
        if append_incremental_field and "LastChangedDateTimeOffset" not in settings.read.fields:
            fields += ",LastChangedDateTimeOffset"
    else:
        fields = None

    if last_modified_date and append_incremental_field:
        params["lastChangedDateTimeOffsetGreaterThan"] = last_modified_date
    if fields:
        params["Fields"] = fields
    if settings.read.filters:
        params.update({key: value for key, value in settings.read.filters.items() if key not in _PROVIDER_FILTER_KEYS})
    if as_of is not None:
        params["date"] = as_of
    return params


def build_url(*, host: str, api_version: str, data_product: str) -> str:
    """Build the PowerOfficeGo API URL for ``data_product``."""
    base_url = host.rstrip("/") + "/"
    version = api_version.strip("/")
    endpoint = str(EndpointInfo.get_endpoint_for_product(data_product)).strip("/")
    url = base_url + "/".join((version, endpoint))
    logger.debug("Constructed URL for PowerOfficeGo API request: %s", url)
    return str(url)
