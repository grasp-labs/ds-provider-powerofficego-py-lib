"""
**File:** ``test_powerofficego_dataset.py``
**Region:** ``tests/dataset/test_powerofficego_dataset``

This module contains tests for the PowerOfficeGo dataset implementation. It includes tests for
data fetching, pagination handling, and error handling to ensure that the PowerOfficeGo dataset
functions correctly under various scenarios.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from ds_resource_plugin_py_lib.common.resource.dataset.errors import ReadError
from ds_resource_plugin_py_lib.common.resource.errors import NotSupportedError

from ds_provider_powerofficego_py_lib.dataset.powerofficego import PowerOfficeGoDataset, PowerOfficeGoDatasetSettings
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
        DummyResponse([{"id": 1}], headers={"X-Pagination": '{"nextPageLink": "exists"}'}),
        DummyResponse([{"id": 2}], headers={"X-Pagination": "{}"}),
    ]
    session = DummySession(responses)
    ds = make_dataset()
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    # Use correct param names to match implementation
    ds._build_params = MagicMock(side_effect=lambda page: {"PageNumber": page, "PageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
        ds.read()
        assert isinstance(ds.output, pd.DataFrame)
        assert set(ds.output["id"]) == {1, 2}
        assert ds.checkpoint["last_page"] == 2


def test_read_error_raises(monkeypatch):
    session = MagicMock()
    session.get.side_effect = Exception("API failure")
    ds = make_dataset()
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(return_value={"pageNumber": 0, "pageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)), pytest.raises(ReadError):
        ds.read()


def test_read_missing_data_product():
    ds = make_dataset(data_product=None)
    with (
        patch.object(type(ds.linked_service), "connection", new=property(lambda self: MagicMock())),
        pytest.raises(NotSupportedError),
    ):
        ds.read()


def test_checkpoint_resume(monkeypatch):
    responses = [
        DummyResponse([{"id": 3}], headers={"X-Pagination": "{}"}),
    ]
    session = DummySession(responses)
    checkpoint = {"last_page": 1, "from_date": "2024-01-01"}
    ds = make_dataset(checkpoint=checkpoint)
    ds._build_url = MagicMock(return_value="https://goapi.poweroffice.net/v2/endpoint")
    ds._build_params = MagicMock(side_effect=lambda page: {"PageNumber": page, "PageSize": 20000})
    with patch.object(type(ds.linked_service), "connection", new=property(lambda self: session)):
        ds.read()
        assert ds.output["id"].iloc[0] == 3
        assert ds.checkpoint["last_page"] == 2


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
    cp = ds._build_checkpoint(5)
    assert cp["last_page"] == 5
    assert cp["data_product"] == ds.settings.data_product


def test_build_checkpoint_no_data_product():
    ds = make_dataset(data_product=None)
    with pytest.raises(ValueError):
        ds._build_checkpoint(1)


def test_build_params_all_fields():
    ds = make_dataset()
    ds.settings.read.from_date = "2024-01-01"
    ds.settings.read.to_date = "2024-01-31"
    ds.settings.read.fields = "id,name"
    params = ds._build_params(2)
    assert params["PageNumber"] == 2
    assert params["fromDate"] == "2024-01-01"
    assert params["toDate"] == "2024-01-31"
    assert params["Fields"] == "id,name"


def test_build_url():
    ds = make_dataset()
    # Patch EndpointInfo.get_endpoint_for_product to return a known endpoint
    with patch(
        "ds_provider_powerofficego_py_lib.dataset.powerofficego.EndpointInfo.get_endpoint_for_product",
        return_value="endpoint-path",
    ):
        url = ds._build_url()
    assert "endpoint-path" in url


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
