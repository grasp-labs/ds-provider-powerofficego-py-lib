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

from ..enums import ResourceType
from ..linked_service.powerofficego import PowerOfficeGoLinkedService
from .products import trial_balance
from .utils import (
    build_checkpoint,
    build_params,
    build_url,
    greatest_incremental_value,
    records_from_body,
)

logger = Logger.get_logger(__name__, package=True)


@dataclass(kw_only=True)
class ReadSettings(Serializable):
    """
    Settings for reading from PowerOfficeGo dataset.

    Attributes:
        page_size (int): Number of records to read per page. Default is 20,000.
        fields (list[str] | None): List of fields to include in the response. Optional.
        filters (dict[str, Any] | None): Query filters for the API request. Optional.
            Product-specific keys (see ``TrialBalanceFilter``) are handled by
            product modules and are not forwarded as native query params.
    """

    page_size: int = 20000
    """Number of records to read per page. Default is 20,000."""

    fields: list[str] | None = None
    """List of fields to include in the response. Optional."""

    filters: dict[str, Any] | None = None
    """Filters for the API request / product-specific read window.

    Native PowerOffice query params are passed through. TrialBalance history
    uses ``TrialBalanceFilter.DATE_FROM`` (required) and optional
    ``TrialBalanceFilter.DATE_TO`` (ISO ``YYYY-MM-DD``; defaults to today).

    Example:
        >>> from ds_provider_powerofficego_py_lib.enums import TrialBalanceFilter
        >>> ReadSettings(filters={TrialBalanceFilter.DATE_FROM: "2025-01-01"})
        >>> ReadSettings(filters={
        ...     TrialBalanceFilter.DATE_FROM: "2025-01-01",
        ...     TrialBalanceFilter.DATE_TO: "2025-12-31",
        ... })
        >>> ReadSettings(filters={"date": "2025-12-31"})
    """


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

        The checkpoint is a dictionary that tracks pagination and incremental state:

        - On a full load, ``self.checkpoint`` is expected to be empty (``{}``) or ``None``.
          In this case, :meth:`read` starts from page ``1``.
        - After each successfully read page, ``self.checkpoint`` is updated with at least ``{"last_page": page, ...}``.
        - If incremental loading is possible (i.e., the data contains a ``lastChangedDateTimeOffset`` field),
          the checkpoint will also include an ``incremental`` key with the latest observed value:
           ``{"incremental": {"last_modified_date": ...}}``.
        - On a subsequent run, if ``self.checkpoint`` contains a ``"last_page"`` entry,
          :meth:`read` resumes from ``last_page + 1`` and continues fetching data from the PowerOfficeGo API.
        - If ``self.checkpoint`` contains an ``incremental`` key, the loader will use the stored ``last_modified_date``
          to filter for new/changed records.

        This allows consumers to perform incremental loads by persisting and reusing
        the checkpoint between executions, avoiding re-reading pages that were already processed successfully.
        The checkpoint structure is designed to support both paginated and incremental (watermark-based) loading.

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
        logger.info("Reading data from PowerOfficeGo dataset with settings: %s", self.settings)
        session = self.linked_service.connection
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

    def _resume_point(self) -> tuple[str | None, int]:
        """
        Derive the incremental watermark and starting page from ``self.checkpoint``.

        Returns:
            tuple[str | None, int]: ``(last_modified_date, page)``. A full load returns ``(None, 1)``.
        """
        last_modified_date = None
        if self.checkpoint and "incremental" in self.checkpoint:
            last_modified_date = self.checkpoint["incremental"].get("value")
            logger.info("Resuming from checkpoint with from_date: %s", last_modified_date)

        page = self.checkpoint["pagination"].get("value", 0) + 1 if self.checkpoint and "pagination" in self.checkpoint else 1
        logger.info("%s load from page %s", "Resuming incremental" if self.checkpoint else "Starting full", page)
        return last_modified_date, page

    def _fetch_data(self, session: Any) -> None:
        """
        Fetch data from PowerOfficeGo API using the provided session.

        Product modules may take over for specialized reads (e.g. TrialBalance
        history via ``filters.date_from``). Other products keep the single
        paginated read.

        Args:
            session (Any): The session object to use for making API requests.
        Raises:
            ReadError: If there is an error during the data fetching process.
        """
        logger.info("Fetching data from PowerOfficeGo API for data product: %s", self.settings.data_product)
        filters = self.settings.read.filters
        trial_balance.reject_if_misused(data_product=self.settings.data_product, filters=filters)
        if trial_balance.handles(data_product=self.settings.data_product, filters=filters):
            trial_balance.fetch_history(self, session)
            return

        last_modified_date, page = self._resume_point()

        all_records: list[dict[str, Any]] = []
        last_successful_page = page - 1
        ls_settings = self.linked_service.settings

        try:
            while True:
                params = build_params(self.settings, page, last_modified_date=last_modified_date)
                url = build_url(
                    host=ls_settings.host,
                    api_version=ls_settings.api_version,
                    data_product=self.settings.data_product,
                )
                logger.debug("Making API request to %s with params: %s", url, params)
                response = session.get(url=url, params=params)
                if response.status_code == 204:
                    logger.info("Received 204 No Content from API. Ending pagination.")
                    break
                page_records = records_from_body(response.json())
                all_records.extend(page_records)
                logger.info("Fetched page %s with %s records.", page, len(page_records))

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
            logger.error("Error occurred while fetching data: %s", exc)
            # On failure, only set last_page (do not update incremental/last_modified_date)
            self.checkpoint = build_checkpoint(last_successful_page, last_modified_date=last_modified_date)
            raise ReadError(
                message=f"Error occurred while fetching data: {exc}",
                details={
                    "last_successful_page": last_successful_page,
                    "failed_page": page,
                    "data_product": self.settings.data_product,
                    "settings": self.settings,
                },
            ) from exc

        else:
            # A completed read defines a new incremental boundary, so the next
            # run must restart pagination from the beginning of that boundary.
            latest = greatest_incremental_value(
                [record.get("LastChangedDateTimeOffset") for record in all_records if record.get("LastChangedDateTimeOffset")],
                kind="LastChangedDateTimeOffset",
            )
            if latest:
                last_modified_date = latest

            self.output = pd.json_normalize(all_records, sep="_")

            # Remove LastChangedDateTimeOffset if it was only fetched for checkpointing.
            if self.settings.read.fields and "LastChangedDateTimeOffset" not in self.settings.read.fields:
                self.output = self.output.drop(columns="LastChangedDateTimeOffset", errors="ignore")

            # Only advance the checkpoint after the output has been built successfully.
            self.checkpoint = build_checkpoint(0, last_modified_date=last_modified_date)

    def close(self) -> None:
        """
        Release any resources held by the dataset.

        Connection lifecycle is managed by the linked service.
        """
