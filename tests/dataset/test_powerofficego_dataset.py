"""
**File:** ``test_powerofficego_dataset.py``
**Region:** ``tests/dataset/test_powerofficego_dataset``

This module contains tests for the PowerOfficeGo dataset implementation. It includes tests for
data fetching, pagination handling, and error handling to ensure that the PowerOfficeGo dataset
functions correctly under various scenarios.
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from ds_resource_plugin_py_lib.common.resource.dataset.errors import ReadError
from ds_resource_plugin_py_lib.common.resource.errors import NotSupportedError

from ds_provider_powerofficego_py_lib.dataset import utils
from ds_provider_powerofficego_py_lib.dataset.powerofficego import (
    PowerOfficeGoDataset,
    PowerOfficeGoDatasetSettings,
    ReadSettings,
)
from ds_provider_powerofficego_py_lib.dataset.products import trial_balance
from ds_provider_powerofficego_py_lib.enums import DataProduct, TrialBalanceFilter
from ds_provider_powerofficego_py_lib.errors import InvalidIncrementalWatermarkException, UnsupportedIncrementalKindException
from ds_provider_powerofficego_py_lib.linked_service.powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings,
)

BUILD_URL = "ds_provider_powerofficego_py_lib.dataset.powerofficego.build_url"
BUILD_PARAMS = "ds_provider_powerofficego_py_lib.dataset.powerofficego.build_params"
TB_BUILD_URL = "ds_provider_powerofficego_py_lib.dataset.products.trial_balance.build_url"


class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, params):
        self.calls.append((url, params))
        resp = self.responses.pop(0)
        return resp


class DummyResponse:
    def __init__(self, data, headers=None):
        self._data = data
        self.headers = headers or {}
        self.status_code = 200

    def json(self):
        return self._data


def make_linked_service():
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key="appkey", client_id="clientid", subscription_key="subkey", host="goapi.poweroffice.net/", api_version="v2"
    )
    svc = PowerOfficeGoLinkedService(
        id="12345678-1234-5678-1234-1234567890ab", name="pogo-linked-service", version="v1.0.0", settings=settings
    )
    return svc


def make_dataset(checkpoint=None, data_product="TestProduct"):
    settings = PowerOfficeGoDatasetSettings(data_product=data_product)
    linked_service = make_linked_service()
    ds = PowerOfficeGoDataset(
        id="34567890-1234-5678-1234-1234567890ab",
        name="pogo-dataset",
        version="v1.0.0",
        linked_service=linked_service,
        settings=settings,
    )
    ds.checkpoint = checkpoint
    return ds


def test_read_successful_fetch(monkeypatch):
    responses = [
        DummyResponse(
            [{"Id": 1, "LastChangedDateTimeOffset": "2024-01-01T00:00:00"}], headers={"X-Pagination": '{"nextPageLink": "exists"}'}
        ),
        DummyResponse([{"Id": 2, "LastChangedDateTimeOffset": "2024-01-01T00:00:00"}], headers={"X-Pagination": "{}"}),
    ]
    session = DummySession(responses)
    ds = make_dataset()
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/endpoint"),
        patch(
            BUILD_PARAMS,
            side_effect=lambda settings, page, last_modified_date=None, **kwargs: {"PageNumber": page, "PageSize": 20000},
        ),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()
    assert isinstance(ds.output, pd.DataFrame)
    assert set(ds.output["Id"]) == {1, 2}
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert "incremental" in ds.checkpoint
    assert ds.checkpoint["incremental"] == {"value": "2024-01-01T00:00:00"}


def test_read_excludes_incremental_field_when_not_requested():
    responses = [
        DummyResponse(
            [{"Id": 1, "LastChangedDateTimeOffset": "2024-01-01T00:00:00"}],
            headers={"X-Pagination": "{}"},
        )
    ]
    session = DummySession(responses)
    ds = make_dataset()
    ds.settings.read.fields = ["Id"]
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/endpoint"),
        patch(BUILD_PARAMS, return_value={"PageNumber": 1, "PageSize": 20000}),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()

    assert list(ds.output.columns) == ["Id"]
    assert ds.output["Id"].tolist() == [1]
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": "2024-01-01T00:00:00"}


def test_read_error_raises(monkeypatch):
    session = MagicMock()
    session.get.side_effect = Exception("API failure")
    ds = make_dataset()
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/endpoint"),
        patch(BUILD_PARAMS, return_value={"pageNumber": 0, "pageSize": 20000}),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
        pytest.raises(ReadError),
    ):
        ds.read()


def test_checkpoint_resume(monkeypatch):
    responses = [
        DummyResponse([{"Id": 3}], headers={"X-Pagination": "{}"}),
    ]
    session = DummySession(responses)
    checkpoint = {"pagination": {"value": 1}, "incremental": {"value": "2024-01-01T00:00:00"}}
    ds = make_dataset(checkpoint=checkpoint)
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/endpoint"),
        patch(
            BUILD_PARAMS,
            side_effect=lambda settings, page, last_modified_date=None, **kwargs: {"PageNumber": page, "PageSize": 20000},
        ),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()
    assert ds.output["Id"].iloc[0] == 3
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert "incremental" in ds.checkpoint


def test_create_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.create()


def test_delete_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.delete()


def test_update_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.update()


def test_rename_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.rename()


def test_list_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.list()


def test_upsert_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.upsert()


def test_purge_not_supported():
    ds = make_dataset()
    with pytest.raises(NotSupportedError):
        ds.purge()


def test_build_checkpoint_success():
    cp = utils.build_checkpoint(5, "2024-01-01T00:00:00")
    assert cp["incremental"] == {"value": "2024-01-01T00:00:00"}
    assert cp["pagination"] == {"value": 5}


def test_successful_read_resets_pagination_for_next_incremental_boundary():
    responses = [
        DummyResponse(
            [{"Id": 1, "LastChangedDateTimeOffset": "2024-01-02T00:00:00"}],
            headers={"X-Pagination": "{}"},
        )
    ]
    session = DummySession(responses)
    checkpoint = {"pagination": {"value": 1}, "incremental": {"value": "2024-01-01T00:00:00"}}
    ds = make_dataset(checkpoint=checkpoint)
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/endpoint"),
        patch(
            BUILD_PARAMS,
            side_effect=lambda settings, page, last_modified_date=None, **kwargs: {"PageNumber": page, "PageSize": 20000},
        ),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()

    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": "2024-01-02T00:00:00"}


def test_build_params_all_fields():
    ds = make_dataset()
    ds.settings.read.fields = ["Id", "Name"]
    ds.settings.read.filters = {"CustomFilter": "value"}
    params = utils.build_params(ds.settings, 2, "2024-01-01T00:00:00")
    assert params["PageNumber"] == 2
    assert params["lastChangedDateTimeOffsetGreaterThan"] == "2024-01-01T00:00:00"
    assert params["Fields"] == "Id,Name,LastChangedDateTimeOffset"
    assert params["CustomFilter"] == "value"


def test_build_url():
    with patch(
        "ds_provider_powerofficego_py_lib.dataset.utils.EndpointInfo.get_endpoint_for_product",
        return_value="endpoint-path",
    ):
        url = utils.build_url(host="goapi.poweroffice.net/", api_version="v2", data_product="TestProduct")
    assert "endpoint-path" in url


def test_type_property():
    ds = make_dataset()
    assert ds.type.name == "POWEROFFICEGO_DATASET"


def test_supports_checkpoint_property():
    ds = make_dataset()
    assert ds.supports_checkpoint is True


def test__fetch_data_no_pagination_header():
    responses = [DummyResponse([{"Id": 1, "LastChangedDateTimeOffset": "2024-01-01T00:00:00"}], headers={})]
    session = DummySession(responses)
    ds = make_dataset()
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/endpoint"),
        patch(
            BUILD_PARAMS,
            side_effect=lambda settings, page, last_modified_date=None, **kwargs: {"PageNumber": page, "PageSize": 20000},
        ),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()
    assert ds.output["Id"].iloc[0] == 1
    assert ds.checkpoint["pagination"] == {"value": 0}


def test_read_204_no_content_sets_empty_output_and_no_raise():
    responses = [DummyResponse([], headers={})]
    responses[0].status_code = 204
    session = DummySession(responses)
    ds = make_dataset()
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/Employees"),
        patch(
            BUILD_PARAMS,
            side_effect=lambda settings, page, last_modified_date=None, **kwargs: {"PageNumber": page, "PageSize": 5000},
        ),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()

    assert isinstance(ds.output, pd.DataFrame)
    assert ds.output.empty is True
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": None}


def test_parse_iso8601_timestamp_fractional_no_tz():
    ts = "2024-05-13T12:34:56.1234567"
    dt = utils.parse_iso8601_timestamp(ts)
    assert dt.microsecond == 123456


def test_greatest_time_field_value_empty():
    assert utils.greatest_time_field_value([]) is None


def test_parse_iso8601_timestamp_basic():
    ts = "2024-05-13T12:34:56Z"
    dt = utils.parse_iso8601_timestamp(ts)
    assert dt == datetime(2024, 5, 13, 12, 34, 56, tzinfo=timezone.utc)


def test_parse_iso8601_timestamp_fractional():
    ts = "2024-05-13T12:34:56.1234567Z"
    dt = utils.parse_iso8601_timestamp(ts)
    assert dt.microsecond == 123456


def test_parse_iso8601_timestamp_offset():
    ts = "2024-05-13T12:34:56+02:00"
    dt = utils.parse_iso8601_timestamp(ts)
    assert dt.hour == 10  # UTC
    assert dt.tzinfo == timezone.utc


def test_parse_iso8601_timestamp_invalid():
    with pytest.raises(InvalidIncrementalWatermarkException):
        utils.parse_iso8601_timestamp("not-a-date")


def test_greatest_time_field_value():
    vals = ["2024-05-13T12:34:56Z", "2024-05-13T13:34:56Z", "2024-05-13T11:34:56Z"]
    result = utils.greatest_time_field_value(vals)
    assert result == "2024-05-13T13:34:56Z"


def test_greatest_time_field_value_invalid():
    vals = [123, "2024-05-13T13:34:56Z"]
    with pytest.raises(InvalidIncrementalWatermarkException):
        utils.greatest_time_field_value(vals)


def test_greatest_incremental_value_time_field():
    vals = ["2024-05-13T12:34:56Z", "2024-05-13T13:34:56Z"]
    result = utils.greatest_incremental_value(vals, kind="LastChangedDateTimeOffset")
    assert result == "2024-05-13T13:34:56Z"


def test_greatest_incremental_value_unsupported():
    vals = ["foo", "bar"]
    with pytest.raises(UnsupportedIncrementalKindException):
        utils.greatest_incremental_value(vals, kind="unknown_kind")


def test_close():
    ds = make_dataset()
    ds.close()


def test__fetch_data_error(monkeypatch):
    ds = make_dataset()
    session = MagicMock()
    session.get.side_effect = Exception("fail")
    with (
        patch(BUILD_URL, return_value="url"),
        patch(BUILD_PARAMS, return_value={}),
        pytest.raises(ReadError),
    ):
        ds._fetch_data(session)
    assert "pagination" in ds.checkpoint
    assert ds.checkpoint["incremental"] == {"value": None}


def test_month_end_as_of_dates():
    dates = list(trial_balance.month_end_as_of_dates(date_from=date(2024, 1, 15), date_to=date(2024, 3, 10)))
    assert dates == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 10)]


def test_resolve_date_from_iso_only():
    assert trial_balance.resolve_date_from(
        {TrialBalanceFilter.DATE_FROM: "2025-01-01"}, data_product=DataProduct.TRIAL_BALANCE
    ) == date(2025, 1, 1)

    with pytest.raises(ReadError):
        trial_balance.resolve_date_from({TrialBalanceFilter.DATE_FROM: "2"}, data_product=DataProduct.TRIAL_BALANCE)

    with pytest.raises(ReadError):
        trial_balance.resolve_date_from({TrialBalanceFilter.DATE_FROM: "not-a-date"}, data_product=DataProduct.TRIAL_BALANCE)


def test_resolve_date_to_optional_defaults():
    assert trial_balance.resolve_date_to({}, data_product=DataProduct.TRIAL_BALANCE, default=date(2026, 10, 15)) == date(
        2026, 10, 15
    )
    assert trial_balance.resolve_date_to(
        {TrialBalanceFilter.DATE_TO: "2025-06-30"},
        data_product=DataProduct.TRIAL_BALANCE,
        default=date(2026, 10, 15),
    ) == date(2025, 6, 30)

    with pytest.raises(ReadError):
        trial_balance.resolve_date_to(
            {TrialBalanceFilter.DATE_TO: "nope"},
            data_product=DataProduct.TRIAL_BALANCE,
            default=date(2026, 10, 15),
        )


def test_date_from_rejected_for_non_trial_balance():
    settings = PowerOfficeGoDatasetSettings(
        data_product="Customers",
        read=ReadSettings(filters={TrialBalanceFilter.DATE_FROM: "2025-01-01"}),
    )
    linked_service = make_linked_service()
    ds = PowerOfficeGoDataset(
        id="34567890-1234-5678-1234-1234567890ab",
        name="pogo-dataset",
        version="v1.0.0",
        linked_service=linked_service,
        settings=settings,
    )
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: MagicMock())), pytest.raises(ReadError):
        ds.read()


def test_trial_balance_history_stamps_date(monkeypatch):
    as_of_dates = [date(2024, 1, 31), date(2024, 2, 29)]
    monkeypatch.setattr(
        "ds_provider_powerofficego_py_lib.dataset.products.trial_balance.month_end_as_of_dates",
        lambda **kwargs: iter(as_of_dates),
    )
    monkeypatch.setattr(
        "ds_provider_powerofficego_py_lib.dataset.products.trial_balance.resolve_date_from",
        lambda filters, *, data_product: date(2024, 1, 1),
    )
    responses = [
        DummyResponse([{"accountNo": 1000, "balance": 1.0}], headers={}),
        DummyResponse([{"accountNo": 1000, "balance": 2.0}], headers={}),
    ]
    session = DummySession(responses)
    settings = PowerOfficeGoDatasetSettings(
        data_product=DataProduct.TRIAL_BALANCE,
        read=ReadSettings(
            filters={TrialBalanceFilter.DATE_FROM: "2024-01-01"},
            fields=["accountNo", "balance"],
        ),
    )
    linked_service = make_linked_service()
    ds = PowerOfficeGoDataset(
        id="34567890-1234-5678-1234-1234567890ab",
        name="pogo-dataset",
        version="v1.0.0",
        linked_service=linked_service,
        settings=settings,
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()
    assert list(ds.output["date"]) == ["2024-01-31", "2024-02-29"]
    assert list(ds.output["balance"]) == [1.0, 2.0]
    assert session.calls[0][1]["date"] == "2024-01-31"
    assert session.calls[1][1]["date"] == "2024-02-29"
    assert TrialBalanceFilter.DATE_FROM not in session.calls[0][1]


def test_build_params_as_of_overrides_filters():
    ds = make_dataset()
    ds.settings.read.filters = {"date": "2020-01-01"}
    params = utils.build_params(ds.settings, 1, None, as_of="2024-12-31")
    assert params["date"] == "2024-12-31"


def test_build_params_strips_trial_balance_date_window():
    ds = make_dataset()
    ds.settings.data_product = DataProduct.TRIAL_BALANCE
    ds.settings.read.filters = {
        TrialBalanceFilter.DATE_FROM: "2025-01-01",
        TrialBalanceFilter.DATE_TO: "2025-12-31",
        "agricultureDepartments": "None",
    }
    params = utils.build_params(ds.settings, 1, None, as_of="2025-01-31")
    assert TrialBalanceFilter.DATE_FROM not in params
    assert TrialBalanceFilter.DATE_TO not in params
    assert params["date"] == "2025-01-31"
    assert params["agricultureDepartments"] == "None"


def test_build_params_trial_balance_does_not_append_last_changed():
    ds = make_dataset(data_product=DataProduct.TRIAL_BALANCE)
    ds.settings.read.fields = ["AccountNo", "AccountName", "Balance"]
    params = utils.build_params(ds.settings, 1, None, as_of="2025-01-31")
    assert params["Fields"] == "AccountNo,AccountName,Balance"
    assert "LastChangedDateTimeOffset" not in params["Fields"]


def make_trial_balance_dataset(filters):
    settings = PowerOfficeGoDatasetSettings(
        data_product=DataProduct.TRIAL_BALANCE,
        read=ReadSettings(filters=filters),
    )
    return PowerOfficeGoDataset(
        id="34567890-1234-5678-1234-1234567890ab",
        name="pogo-dataset",
        version="v1.0.0",
        linked_service=make_linked_service(),
        settings=settings,
    )


def test_reject_if_misused_ignores_unrelated_filters():
    trial_balance.reject_if_misused(data_product="Customers", filters={"CustomFilter": "value"})


def test_resolve_date_from_is_required():
    with pytest.raises(ReadError):
        trial_balance.resolve_date_from({}, data_product=DataProduct.TRIAL_BALANCE)


def test_resolve_date_from_rejects_non_string():
    with pytest.raises(ReadError):
        trial_balance.resolve_date_from({TrialBalanceFilter.DATE_FROM: 20250101}, data_product=DataProduct.TRIAL_BALANCE)


def test_month_end_as_of_dates_empty_when_from_is_after_to():
    assert list(trial_balance.month_end_as_of_dates(date_from=date(2024, 3, 1), date_to=date(2024, 1, 1))) == []


def test_trial_balance_history_rejects_inverted_date_range():
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2025-12-31", TrialBalanceFilter.DATE_TO: "2025-01-01"},
    )
    with (
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: MagicMock())),
        pytest.raises(ReadError),
    ):
        ds.read()


def test_trial_balance_history_skips_as_of_date_on_204():
    no_content = DummyResponse([], headers={})
    no_content.status_code = 204
    session = DummySession([no_content, DummyResponse([{"accountNo": 1000, "balance": 2.0}], headers={})])
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2024-01-01", TrialBalanceFilter.DATE_TO: "2024-02-29"},
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()
    assert [call[1]["date"] for call in session.calls] == ["2024-01-31", "2024-02-29"]
    assert list(ds.output["date"]) == ["2024-02-29"]


def test_trial_balance_history_follows_pagination():
    session = DummySession(
        [
            DummyResponse([{"accountNo": 1000, "balance": 1.0}], headers={"X-Pagination": '{"nextPageLink": "next"}'}),
            DummyResponse([{"accountNo": 2000, "balance": 2.0}], headers={"X-Pagination": "{}"}),
        ]
    )
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2024-01-01", TrialBalanceFilter.DATE_TO: "2024-01-31"},
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
    ):
        ds.read()
    assert [call[1]["PageNumber"] for call in session.calls] == [1, 2]
    assert list(ds.output["accountNo"]) == [1000, 2000]
    # A finished read means "start from page 1 next time", even when it walked several pages.
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": None}


def test_trial_balance_history_wraps_unexpected_errors():
    session = MagicMock()
    session.get.side_effect = RuntimeError("boom")
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2024-01-01", TrialBalanceFilter.DATE_TO: "2024-01-31"},
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
        pytest.raises(ReadError),
    ):
        ds.read()
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": None}


def test_trial_balance_history_reraises_read_errors_unchanged():
    original = ReadError(message="upstream", details={})
    session = MagicMock()
    session.get.side_effect = original
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2024-01-01", TrialBalanceFilter.DATE_TO: "2024-01-31"},
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
        pytest.raises(ReadError) as exc_info,
    ):
        ds.read()
    assert exc_info.value is original
    assert not ds.checkpoint


def test_records_from_body_list_keeps_only_dict_rows():
    assert utils.records_from_body([{"Id": 1}, "junk", 2, {"Id": 3}]) == [{"Id": 1}, {"Id": 3}]


@pytest.mark.parametrize("key", ["data", "value", "values"])
def test_records_from_body_unwraps_nested_list(key):
    assert utils.records_from_body({key: [{"Id": 1}, "junk"]}) == [{"Id": 1}]


@pytest.mark.parametrize("body", [{"data": "not-a-list"}, {"other": [{"Id": 1}]}, "text", 5, None])
def test_records_from_body_returns_empty_for_unknown_shapes(body):
    assert utils.records_from_body(body) == []


def test_parse_iso8601_timestamp_short_fraction_is_kept():
    dt = utils.parse_iso8601_timestamp("2024-05-13T12:34:56.123Z")
    assert dt.microsecond == 123000
    assert dt.tzinfo == timezone.utc


def test_trial_balance_handles_any_history_key_even_if_incomplete():
    product = DataProduct.TRIAL_BALANCE
    assert trial_balance.handles(data_product=product, filters={TrialBalanceFilter.DATE_FROM: "2025-01-01"})
    assert trial_balance.handles(data_product=product, filters={TrialBalanceFilter.DATE_TO: "2025-12-31"})
    assert trial_balance.handles(data_product=product, filters={TrialBalanceFilter.DATE_FROM: ""})


def test_trial_balance_does_not_handle_plain_reads():
    product = DataProduct.TRIAL_BALANCE
    assert not trial_balance.handles(data_product=product, filters=None)
    assert not trial_balance.handles(data_product=product, filters={})
    assert not trial_balance.handles(data_product=product, filters={"date": "2025-12-31"})
    assert not trial_balance.handles(data_product="Customers", filters={TrialBalanceFilter.DATE_FROM: "2025-01-01"})


@pytest.mark.parametrize(
    "filters",
    [{TrialBalanceFilter.DATE_TO: "2025-12-31"}, {TrialBalanceFilter.DATE_FROM: ""}],
)
def test_trial_balance_incomplete_history_filters_fail_instead_of_dropping_keys(filters):
    session = MagicMock()
    ds = make_trial_balance_dataset(filters)
    with (
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
        pytest.raises(ReadError),
    ):
        ds.read()
    session.get.assert_not_called()


def test_trial_balance_history_failure_reports_current_as_of_and_does_not_persist_page():
    session = MagicMock()
    session.get.side_effect = [
        DummyResponse([{"AccountNo": 1000}], headers={"X-Pagination": '{"nextPageLink": "next"}'}),
        DummyResponse([{"AccountNo": 2000}], headers={"X-Pagination": "{}"}),
        RuntimeError("boom"),
    ]
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2024-01-01", TrialBalanceFilter.DATE_TO: "2024-02-29"},
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)),
        pytest.raises(ReadError) as exc_info,
    ):
        ds.read()
    # January had two pages; the failure is on February page 1, so nothing carries over from January.
    assert exc_info.value.details["as_of"] == "2024-02-29"
    assert exc_info.value.details["failed_page"] == 1
    assert exc_info.value.details["last_successful_page"] == 0
    assert ds.checkpoint["pagination"] == {"value": 0}


def test_normal_read_after_history_read_starts_from_page_one():
    history_session = DummySession(
        [
            DummyResponse([{"AccountNo": 1000}], headers={"X-Pagination": '{"nextPageLink": "next"}'}),
            DummyResponse([{"AccountNo": 2000}], headers={"X-Pagination": "{}"}),
        ]
    )
    ds = make_trial_balance_dataset(
        {TrialBalanceFilter.DATE_FROM: "2024-01-01", TrialBalanceFilter.DATE_TO: "2024-01-31"},
    )
    with (
        patch(TB_BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: history_session)),
    ):
        ds.read()

    # Same dataset, same checkpoint, now a plain point-in-time read.
    ds.settings.read.filters = {"date": "2024-01-31"}
    normal_session = DummySession([DummyResponse([{"AccountNo": 1000}], headers={})])
    with (
        patch(BUILD_URL, return_value="https://goapi.poweroffice.net/v2/TrialBalance"),
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: normal_session)),
    ):
        ds.read()
    assert normal_session.calls[0][1]["PageNumber"] == 1
    assert list(ds.output["AccountNo"]) == [1000]
