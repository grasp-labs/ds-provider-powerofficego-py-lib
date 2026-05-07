"""
**File:** ``02_dataset_read.py``
**Region:** ``examples/02_dataset_read.py``

Example 02: Reading data from PowerOfficeGo.

This example demonstrates:
- Creating a Linked Service and connecting.
- Creating a Dataset for a data product.
- Reading customer data from PowerOfficeGo.
- Handle pagination when reading data.
"""
from __future__ import annotations

import base64
import logging
import os
from uuid import uuid4

from ds_common_logger_py_lib import Logger

from ds_provider_powerofficego_py_lib.linked_service.powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings
)
from ds_provider_powerofficego_py_lib.dataset.powerofficego import (
    ReadSettings,
    PowerOfficeGoDataset,
    PowerOfficeGoDatasetSettings
)

Logger.configure(level=logging.DEBUG)
logger = Logger.get_logger(__name__)


def main() -> None:
    # Create a Linked Service and connect
    linked_service_settings = PowerOfficeGoLinkedServiceSettings(
        application_key=os.getenv("POWEROFFICEGO_APPLICATION_KEY", "your-application-key"),
        client_id=os.getenv("POWEROFFICEGO_CLIENT_ID", "your-client-id"),
        subscription_key=os.getenv("POWEROFFICEGO_SUBSCRIPTION_KEY", "your-subscription-key"),
    )
    linked_service = PowerOfficeGoLinkedService(
        id=uuid4(),
        name="pogo-linked-service",
        version="v1.0.0",
        settings=linked_service_settings,
    )
    # Create a Dataset for a data product customer
    dataset_settings = PowerOfficeGoDatasetSettings(
        data_product="Customers",
        read=ReadSettings(
            page_size=100,
        )
    )
    dataset = PowerOfficeGoDataset(
        id=uuid4(),
        name="pogo-customers-dataset",
        version="v1.0.0",
        linked_service=linked_service,
        settings=dataset_settings,
    )

    try:
        # Connect to PowerOfficeGo
        linked_service.connect()

        logger.info("Reading customer data from PowerOfficeGo...")
        dataset.read()

        # Access the results
        if dataset.output is not None and not dataset.output.empty:
            logger.info("✓ Read %d customers", len(dataset.output))
            logger.debug("Columns: %s", list(dataset.output.columns))
            logger.debug("First few rows:\n%s", dataset.output.head())
        else:
            logger.info("No customer data returned")

        # The checkpoint can be persisted for incremental loads
        if dataset.supports_checkpoint and dataset.checkpoint:
            logger.debug("Checkpoint for next run: %s", dataset.checkpoint)

    except Exception as exc:
        logger.error("Failed to read data: %s", exc)
        raise

    finally:
        # Clean up
        linked_service.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    main()
