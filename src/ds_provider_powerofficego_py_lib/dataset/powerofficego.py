"""
**File:** ``powerofficego.py``
**Region:** ``ds_provider_powerofficego_py_lib/dataset/powerofficego``

This module contains dataset-related classes and functions for the PowerOfficeGo provider.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

import pandas as pd
from ds_common_logger_py_lib import Logger
from ds_common_serde_py_lib import Serializable
from ds_resource_plugin_py_lib.common.resource.dataset import DatasetSettings, DatasetStorageFormatType, TabularDataset
from ds_resource_plugin_py_lib.common.resource.dataset.errors import (
    ReadError,
)
from ds_resource_plugin_py_lib.common.resource.errors import NotSupportedError
from ds_resource_plugin_py_lib.common.serde.deserialize import PandasDeserializer
from ds_resource_plugin_py_lib.common.serde.serialize import PandasSerializer

from ..endpoint_info import EndpointInfo
from ..enums import ResourceType
from ..linked_service.powerofficego import PowerOfficeGoLinkedService

logger = Logger.get_logger(__name__, package=True)


@dataclass(kw_only=True)
class ReadSettings(Serializable):
    """
    Settings for reading from PowerOfficeGo dataset.

    Attributes:
        page_size (int): Number of records to read per page. Default is 20,000.
        from_date (str | None): Start date for filtering records. Format: 'YYYY-MM-DD'. Optional.
        to_date (str | None): End date for filtering records. Format: 'YYYY-MM-DD'. Optional.
        fields (list[str] | None): List of fields to include in the response. Optional.
    """

    page_size: int = 20000
    """Number of records to read per page. Default is 20,000."""

    last_modified_date: str | None = None
    """Filter records by last modified date. Format: 'YYYY-MM-DDTHH:MM:SS'. Optional."""

    fields: list[str] | None = None
    """List of fields to include in the response. Optional."""

    filters: dict[str, Any] | None = None
    """Additional filters for the API request. Optional."""


@dataclass(kw_only=True)
class PowerOfficeGoDatasetSettings(DatasetSettings):
    """
    Settings for PowerOfficeGo dataset.

    Attributes:
        data_product (str): Data product to read from PowerOfficeGo API. Required. Must match product name as used in DS Config.
        read (ReadSettings): Settings for reading from PowerOfficeGo dataset. Contains pagination and filtering options.
    """

    data_product: str
    """Data product to read from PowerOfficeGo API. Required. Must match product name as used in DS Config."""

    read: ReadSettings = field(default_factory=ReadSettings)
    """Settings for reading from PowerOfficeGo dataset."""


PowerOfficeGoDatasetSettingsType = TypeVar("PowerOfficeGoDatasetSettingsType", bound=PowerOfficeGoDatasetSettings)
PowerOfficeGoLinkedServiceType = TypeVar("PowerOfficeGoLinkedServiceType", bound=PowerOfficeGoLinkedService[Any])


@dataclass(kw_only=True)
class PowerOfficeGoDataset(
    TabularDataset[PowerOfficeGoLinkedServiceType, PowerOfficeGoDatasetSettingsType, PandasSerializer, PandasDeserializer],
    Generic[PowerOfficeGoLinkedServiceType, PowerOfficeGoDatasetSettingsType],
):
    """
    PowerOfficeGoDataset represents a dataset for the PowerOfficeGo provider.

    Attributes:
        linked_service (PowerOfficeGoLinkedServiceType): The linked service used to connect to PowerOfficeGo.
        settings (PowerOfficeGoDatasetSettingsType): The settings for the dataset, including data product and read settings.
        serializer (PandasSerializer | None): The serializer used for the dataset. Defaults to JSON format.
        deserializer (PandasDeserializer | None): The deserializer used for the dataset. Defaults to JSON format.
    """

    linked_service: PowerOfficeGoLinkedServiceType
    settings: PowerOfficeGoDatasetSettingsType

    serializer: PandasSerializer | None = field(default_factory=lambda: PandasSerializer(format=DatasetStorageFormatType.JSON))
    deserializer: PandasDeserializer | None = field(
        default_factory=lambda: PandasDeserializer(format=DatasetStorageFormatType.JSON)
    )

    @property
    def type(self) -> ResourceType:
        return ResourceType.POWEROFFICEGO_DATASET

    @property
    def supports_checkpoint(self) -> bool:
        """
        Whether this provider supports incremental loads via ``self.checkpoint``.

        This implementation uses a simple dictionary-based checkpoint structure to
        support resuming paginated reads:

        - On a full load, ``self.checkpoint`` is expected to be empty (``{}``) or
          ``None``. In this case, :meth:`read` starts from page ``1``.
        - After each successfully read page, :meth:`read` sets
          ``self.checkpoint = {"last_page": page}``, where ``page`` is the last
          completed page number.
        - On a subsequent run, if ``self.checkpoint`` contains a ``"last_page"``
          entry, :meth:`read` resumes from ``last_page + 1`` and continues
          fetching data from the PowerOfficeGo API.

        This allows consumers to perform incremental loads by persisting and
        reusing the checkpoint between executions, avoiding re-reading pages that
        were already processed successfully.

        Returns:
             bool: True if checkpointing is supported, False otherwise.
        """
        return True

    def read(self) -> None:
        """
        Read data from PowerOfficeGo API from requested endpoint.

        Raises:
            ReadError: If there is an error during the read operation.
        """
        logger.info(f"Reading data from PowerOfficeGo dataset with settings: {self.settings}")
        session = self.linked_service.connection

        if self.settings.data_product is None:
            raise NotSupportedError("Data product must be provided.")

        self._fetch_data(session=session)

    def create(self) -> None:
        raise NotSupportedError("Method create is not supported by PowerOfficeGo provider.")

    def delete(self) -> None:
        raise NotSupportedError("Method delete is not supported by PowerOfficeGo provider.")

    def update(self) -> None:
        raise NotSupportedError("Method update is not supported by PowerOfficeGo provider.")

    def rename(self) -> None:
        raise NotSupportedError("Method rename is not supported by PowerOfficeGo provider.")

    def list(self) -> None:
        raise NotSupportedError("Method list is not supported by PowerOfficeGo provider.")

    def upsert(self) -> None:
        raise NotSupportedError("Method upsert is not supported by PowerOfficeGo provider.")

    def purge(self) -> None:
        raise NotSupportedError("Method purge is not supported by PowerOfficeGo provider.")

    def _fetch_data(self, session: Any) -> None:
        """
        Fetch data from PowerOfficeGo API using the provided session.

        Args:
            session (Any): The session object to use for making API requests.
        Raises:
            ReadError: If there is an error during the data fetching process.
        """
        logger.info(f"Fetching data from PowerOfficeGo API for data product: {self.settings.data_product}")
        if self.checkpoint and "incremental" in self.checkpoint:
            logger.info(f"Resuming from checkpoint with from_date: {self.checkpoint['incremental']['last_modified_date']}")
            self.settings.read.last_modified_date = self.checkpoint["incremental"]["last_modified_date"]

        page = self.checkpoint.get("last_page", 0) + 1 if self.checkpoint else 1
        logger.info("%s load from page %s", "Resuming incremental" if self.checkpoint else "Starting full", page)

        all_records: list[dict[str, Any]] = []
        last_successful_page = page - 1

        try:
            if self.settings.data_product is None:
                raise NotSupportedError("Data product must be provided to fetch data.")
            while True:
                params = self._build_params(page)
                url = self._build_url()
                logger.debug(f"Making API request to {url} with params: {params}")
                response = session.get(url=url, params=params)
                data = response.json()
                all_records.extend(data)
                logger.info(f"Fetched page {page} with {len(data)} records.")

                last_successful_page = page

                pagination_header = response.headers.get("X-Pagination")
                if pagination_header:
                    pagination = json.loads(pagination_header)
                    next_page = pagination.get("nextPageLink")
                    if not next_page:
                        logger.info("Last page reached based on pagination header. Ending pagination.")
                        break
                else:
                    logger.warning("Pagination header not found in response. Ending pagination to avoid infinite loop.")
                    break

                page += 1

        except Exception as exc:
            logger.error(f"Error occurred while fetching data: {exc}")
            raise ReadError(
                message=f"Error occurred while fetching data: {exc}",
                details={
                    "last_successful_page": last_successful_page,
                    "failed_page": page,
                    "data_product": self.settings.data_product,
                    "settings": self.settings,
                },
            ) from exc

        finally:
            self.output = pd.DataFrame(all_records)
            self.checkpoint = self._build_checkpoint(last_successful_page)

    def _build_checkpoint(self, last_page: int) -> dict[str, Any]:
        """
        Build a checkpoint dictionary to track the last successfully read page.

        Checkpoint structure:
            {
                "last_page": int,
                "last_modified_date": str,
                "page_size": int,
                "data_product": str
            }

        Args:
            last_page (int): The last page number that was successfully read.
        Returns:
            dict[str, Any]: A checkpoint dictionary containing the last page information.
        """
        if self.settings.data_product is None:
            raise ValueError("Data product must be provided to build checkpoint.")

        checkpoint = {
            "incremental": {
                "last_modified_date": self.settings.read.last_modified_date,
            },
            "last_page": last_page,
            "page_size": self.settings.read.page_size,
            "data_product": self.settings.data_product,
        }
        logger.debug(f"Built checkpoint: {checkpoint}")
        return checkpoint

    def _build_params(self, page: int) -> dict[str, Any]:
        """
        Build the query parameters for the PowerOfficeGo API request based on the dataset settings and pagination.

        Args:
            page (int): The page number to fetch.
        Returns:
            dict[str, Any]: A dictionary of query parameters for the API request.
        """
        params: dict[str, Any] = {
            "PageNumber": page,
            "PageSize": self.settings.read.page_size,
        }
        if self.settings.read.last_modified_date:
            params["lastChangedDateTimeOffsetGreaterThan"] = self.settings.read.last_modified_date
        if self.settings.read.fields:
            params["Fields"] = self.settings.read.fields
        if self.settings.read.filters:
            params.update(self.settings.read.filters)
        return params

    def _build_url(self) -> str:
        """
        Build the URL for the PowerOfficeGo API request based on the dataset settings.

        Returns:
            str: The constructed URL for the API request.
        """
        base_url = self.linked_service.settings.host
        api_version = self.linked_service.settings.api_version
        endpoint = EndpointInfo.get_endpoint_for_product(self.settings.data_product)
        url = f"{base_url}{api_version}/{endpoint}"
        logger.debug(f"Constructed URL for PowerOfficeGo API request: {url}")
        return url

    def close(self) -> None:
        """
        Release any resources held by the dataset.

        Connection lifecycle is managed by the linked service.
        """
