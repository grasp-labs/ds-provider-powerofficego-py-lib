"""
**File:** ``03_datasedt_read_trial_balance.py``
**Region:** ``examples/03_datasedt_read_trial_balance.py``

Example 03: Dataset + TrialBalance dataset read.

Usage:
    uv run python examples/03_datasedt_read_trial_balance.py
"""

from __future__ import annotations

import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
from ds_common_logger_py_lib import Logger

from ds_provider_powerofficego_py_lib.dataset.powerofficego import (
    PowerOfficeGoDataset,
    PowerOfficeGoDatasetSettings,
    ReadSettings,
)
from ds_provider_powerofficego_py_lib.enums import DataProduct, TrialBalanceFilter
from ds_provider_powerofficego_py_lib.linked_service.powerofficego import (
    PowerOfficeGoLinkedService,
    PowerOfficeGoLinkedServiceSettings,
)

load_dotenv()

Logger.configure(level=logging.INFO)
logger = Logger.get_logger(__name__)


def main() -> None:
    linked_service = PowerOfficeGoLinkedService(
        id=uuid4(),
        name="pogo-linked-service",
        version="v1.0.0",
        settings=PowerOfficeGoLinkedServiceSettings(
            application_key=os.environ["POWEROFFICEGO_APPLICATION_KEY"],
            client_id=os.environ["POWEROFFICEGO_CLIENT_ID"],
            subscription_key=os.environ["POWEROFFICEGO_SUBSCRIPTION_KEY"],
        ),
    )

    dataset = PowerOfficeGoDataset(
        id=uuid4(),
        name="pogo-trial-balance-dataset",
        version="v1.0.0",
        linked_service=linked_service,
        settings=PowerOfficeGoDatasetSettings(
            data_product=DataProduct.TRIAL_BALANCE,
            read=ReadSettings(
                page_size=5000,
                filters={
                    TrialBalanceFilter.DATE_FROM: "2025-01-01",
                    TrialBalanceFilter.DATE_TO: "2025-12-31",
                },
                fields=["AccountNo", "AccountName", "Balance"],
            ),
        ),
    )

    try:
        linked_service.connect()
        dataset.read()
        logger.info(
            "Read %s rows",
            len(dataset.output) if dataset.output is not None else 0,
        )
        if dataset.output is not None and not dataset.output.empty:
            logger.info("Columns: %s", list(dataset.output.columns))
            logger.info("Head:\n%s", dataset.output.head())
    finally:
        linked_service.close()


if __name__ == "__main__":
    main()
