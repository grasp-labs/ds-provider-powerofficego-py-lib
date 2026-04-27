"""
**File:** ``01_linked_service_connect.py``
**Region:** ``examples/01_linked_service_connect``

Example 01: Connecting a PowerOfficeGo linked service.

This example demonstrates how to create and connect a PowerOfficeGo linked service
using the `PowerOfficeGoLinkedService` class.
It includes the necessary settings for authentication and
connection to the PowerOfficeGo API.

Prerequisites:
    Set environment variables for PowerOfficeGo API authentication:
    - `POGO_APPLICATION_KEY`: Your PowerOfficeGo application key.
    - `POGO_CLIENT_ID`: Your PowerOfficeGo client ID.
    - `POGO_SUBSCRIPTION_KEY`: Your PowerOfficeGo subscription key.
"""

from __future__ import annotations

import os
import logging
from uuid import uuid4

from ds_common_logger_py_lib import Logger
from ds_provider_powerofficego_py_lib.linked_service import PowerOfficeGoLinkedService, PowerOfficeGoLinkedServiceSettings

Logger.configure(level=logging.DEBUG)
logger = Logger.get_logger(__name__)


def main() -> None:
    # Load settings from environment variables
    application_key = os.getenv("POGO_APPLICATION_KEY", "your-application-key")
    client_id = os.getenv("POGO_CLIENT_ID", "your-client-id")
    subscription_key = os.getenv("POGO_SUBSCRIPTION_KEY", "your-subscription-key")

    # Create linked service settings
    settings = PowerOfficeGoLinkedServiceSettings(
        application_key=application_key,
        client_id=client_id,
        subscription_key=subscription_key,
    )

    # Create linked service instance
    linked_service = PowerOfficeGoLinkedService(
        id=uuid4(),
        name="example-pogo-linked-service",
        version="1.0.0",
        settings=settings,
    )

    try:
        # Connect the linked service
        logger.info("Testing connection to PowerOfficeGo linked service...")
        success, message = linked_service.test_connection()

        if success:
            logger.info("✓ Connection test successful!")
            logger.debug("Message: %s", message)
        else:
            logger.error("✗ Connection test failed: %s", message)
            return

    except ConnectionError as exc:
        logger.error("Failed to connect to PowerOfficeGo: %s", exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error: %s", exc)
        raise


if __name__ == "__main__":
    main()
