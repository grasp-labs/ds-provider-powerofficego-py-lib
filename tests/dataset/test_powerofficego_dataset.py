"""
**File:** ``test_powerofficego_dataset.py``
**Region:** ``tests/dataset/test_powerofficego_dataset``

This module contains tests for the PowerOfficeGo dataset implementation. It includes tests for
data fetching, pagination handling, and error handling to ensure that the PowerOfficeGo dataset
functions correctly under various scenarios.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from ds_resource_plugin_py_lib.common.resource.dataset.errors import ReadError
from ds_resource_plugin_py_lib.common.resource.errors import NotSupportedError

from ds_provider_powerofficego_py_lib.dataset.powerofficego import PowerOfficeGoDataset, PowerOfficeGoDatasetSettings
from ds_provider_powerofficego_py_lib.errors import InvalidIncrementalWatermarkException, UnsupportedIncrementalKindException
from ds_provider_powerofficego_py_lib.linked_service.powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings,
)


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
    # Simulate two pages, then end
    responses = [
        DummyResponse(
            [{"Id": 1, "LastChangedDateTimeOffset": "2024-01-01T00:00:00"}], headers={"X-Pagination": '{"nextPageLink": "exists"}'}
        ),
        DummyResponse([{"Id": 2, "LastChangedDateTimeOffset": "2024-01-01T00:00:00"}], headers={"X-Pagination": "{}"}),
    ]
    session = DummySession(responses)
    ds = make_dataset()
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(side_effect=lambda page, last_modified_date=None: {"PageNumber": page, "PageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
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
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(return_value={"PageNumber": 1, "PageSize": 20000})

    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
        ds.read()

    assert list(ds.output.columns) == ["Id"]
    assert ds.output["Id"].tolist() == [1]
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": "2024-01-01T00:00:00"}


def test_read_error_raises(monkeypatch):
    session = MagicMock()
    session.get.side_effect = Exception("API failure")
    ds = make_dataset()
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(return_value={"pageNumber": 0, "pageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)), pytest.raises(ReadError):
        ds.read()


def test_checkpoint_resume(monkeypatch):
    responses = [
        DummyResponse([{"Id": 3}], headers={"X-Pagination": "{}"}),
    ]
    session = DummySession(responses)
    checkpoint = {"pagination": {"value": 1}, "incremental": {"value": "2024-01-01T00:00:00"}}
    ds = make_dataset(checkpoint=checkpoint)
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(side_effect=lambda page, last_modified_date=None: {"PageNumber": page, "PageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
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
    ds = make_dataset()
    cp = ds._build_checkpoint(5, "2024-01-01T00:00:00")
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
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(side_effect=lambda page, last_modified_date=None: {"PageNumber": page, "PageSize": 20000})

    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
        ds.read()

    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": "2024-01-02T00:00:00"}


def test_build_params_all_fields():
    ds = make_dataset()
    ds.settings.read.fields = ["Id", "Name"]
    ds.settings.read.filters = {"CustomFilter": "value"}
    params = ds._build_params(2, "2024-01-01T00:00:00")
    assert params["PageNumber"] == 2
    assert params["lastChangedDateTimeOffsetGreaterThan"] == "2024-01-01T00:00:00"
    assert params["Fields"] == "Id,Name,LastChangedDateTimeOffset"
    assert params["CustomFilter"] == "value"


def test_build_url():
    ds = make_dataset()
    # Patch EndpointInfo.get_endpoint_for_product to return a known endpoint
    with patch(
        "ds_provider_powerofficego_py_lib.dataset.powerofficego.EndpointInfo.get_endpoint_for_product",
        return_value="endpoint-path",
    ):
        url = ds._build_url()
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
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(side_effect=lambda page, last_modified_date=None: {"PageNumber": page, "PageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
        ds.read()
        assert ds.output["Id"].iloc[0] == 1
        assert ds.checkpoint["pagination"] == {"value": 0}


def test_read_204_no_content_sets_empty_output_and_no_raise():
    responses = [DummyResponse([], headers={})]
    responses[0].status_code = 204
    session = DummySession(responses)
    ds = make_dataset()
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/Employees")
    ds._build_params = MagicMock(side_effect=lambda page, last_modified_date=None: {"PageNumber": page, "PageSize": 5000})

    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
        ds.read()

    assert isinstance(ds.output, pd.DataFrame)
    assert ds.output.empty is True
    assert ds.checkpoint["pagination"] == {"value": 0}
    assert ds.checkpoint["incremental"] == {"value": None}


def test_parse_iso8601_timestamp_fractional_no_tz():
    ds = make_dataset()
    # 7 digits, no timezone
    ts = "2024-05-13T12:34:56.1234567"
    dt = ds._parse_iso8601_timestamp(ts)
    assert dt.microsecond == 123456


def test_greatest_time_field_value_empty():
    ds = make_dataset()
    assert ds._greatest_time_field_value([]) is None


def test_parse_iso8601_timestamp_basic():
    ds = make_dataset()
    # Basic UTC
    ts = "2024-05-13T12:34:56Z"
    dt = ds._parse_iso8601_timestamp(ts)
    assert dt == datetime(2024, 5, 13, 12, 34, 56, tzinfo=timezone.utc)


def test_parse_iso8601_timestamp_fractional():
    ds = make_dataset()
    # 7 digits, should truncate to 6
    ts = "2024-05-13T12:34:56.1234567Z"
    dt = ds._parse_iso8601_timestamp(ts)
    assert dt.microsecond == 123456


def test_parse_iso8601_timestamp_offset():
    ds = make_dataset()
    ts = "2024-05-13T12:34:56+02:00"
    dt = ds._parse_iso8601_timestamp(ts)
    assert dt.hour == 10  # UTC
    assert dt.tzinfo == timezone.utc


def test_parse_iso8601_timestamp_invalid():
    ds = make_dataset()
    with pytest.raises(InvalidIncrementalWatermarkException):
        ds._parse_iso8601_timestamp("not-a-date")


def test_greatest_time_field_value():
    ds = make_dataset()
    vals = ["2024-05-13T12:34:56Z", "2024-05-13T13:34:56Z", "2024-05-13T11:34:56Z"]
    result = ds._greatest_time_field_value(vals)
    assert result == "2024-05-13T13:34:56Z"


def test_greatest_time_field_value_invalid():
    ds = make_dataset()
    vals = [123, "2024-05-13T13:34:56Z"]
    with pytest.raises(InvalidIncrementalWatermarkException):
        ds._greatest_time_field_value(vals)


def test_greatest_incremental_value_time_field():
    ds = make_dataset()
    vals = ["2024-05-13T12:34:56Z", "2024-05-13T13:34:56Z"]
    result = ds.greatest_incremental_value(vals, kind="LastChangedDateTimeOffset")
    assert result == "2024-05-13T13:34:56Z"


def test_greatest_incremental_value_unsupported():
    ds = make_dataset()
    vals = ["foo", "bar"]
    with pytest.raises(UnsupportedIncrementalKindException):
        ds.greatest_incremental_value(vals, kind="unknown_kind")


def test_close():
    ds = make_dataset()
    # Should not raise
    ds.close()


def test__fetch_data_error(monkeypatch):
    ds = make_dataset()
    session = MagicMock()
    session.get.side_effect = Exception("fail")
    # Patch _build_url/_build_params to avoid unrelated errors
    ds._build_url = MagicMock(return_value="url")
    ds._build_params = MagicMock(return_value={})
    with pytest.raises(ReadError):
        ds._fetch_data(session)
    # Should set checkpoint with last_page only (no incremental)
    assert "pagination" in ds.checkpoint
    assert ds.checkpoint["incremental"] == {"value": None}
