import logging
import os
import time
from typing import Iterable

import requests
from exponent_server_sdk import (  # type: ignore[reportUnknownParameterType]
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
    PushTicketError,
)
from requests.exceptions import ConnectionError, HTTPError

from .models import NotificationDevice, PushMessageLog

logger = logging.getLogger(__name__)


def _build_push_client() -> PushClient:
    expo_token = os.getenv("EXPO_TOKEN")
    if not expo_token:
        return PushClient()
    session = requests.Session()
    session.headers.update(
        {
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",
            "content-type": "application/json",
            "Authorization": f"Bearer {expo_token}",
        }
    )
    return PushClient(session=session)


def send_push_message_delayed(
    devices: list[NotificationDevice], title: str, body: str, extra: dict | None = None
):
    """Excetute send_push_message but wait 15 seconds."""
    send_push_message(devices, title, body, extra)
    time.sleep(15)


def send_push_message(
    devices: list[NotificationDevice], title: str, body: str, extra: dict | None = None
):
    # Filter out devices that already have a push message with the same title
    devices_to_notify = []
    for device in devices:
        # Check if a push log with the same title already exists for this device
        if not PushMessageLog.objects.filter(
            to=device, body=body, title=title
        ).exists():
            devices_to_notify.append(device)

    # If no devices to notify, return early
    if not devices_to_notify:
        logger.info("No new devices to notify with title=%s", title)
        return

    client = _build_push_client()
    try:
        responses = client.publish_multiple(
            [
                PushMessage(to=device.expo_token, body=body, title=title, data=extra)  # type: ignore[reportUnknownParameterType]
                for device in devices_to_notify
            ]
        )
    except PushServerError as exc:
        # Encountered some likely formatting/validation error.
        logger.error(
            "PushServerError for tokens=%s, message=%s, extra=%s, errors=%s, response_data=%s",
            [d.expo_token for d in devices_to_notify],
            title,
            extra,
            exc.errors,
            exc.response_data,
        )
        raise
    except (ConnectionError, HTTPError):
        # Encountered some Connection or HTTP error - retry a few times in
        # case it is transient.
        logger.warning(
            "Connection/HTTP error for tokens=%s, message=%s, extra=%s",
            [d.expo_token for d in devices_to_notify],
            title,
            extra,
        )
        raise

    # Map responses back to devices
    for i, response in enumerate(responses):
        device = devices_to_notify[i]
        try:
            # We got a response back, but we don't know whether it's an error yet.
            # This call raises errors so we can handle them with normal exception
            # flows.
            response.validate_response()
            PushMessageLog.objects.create(
                to=device,
                body=body,
                title=title,
                data={"ticket": response.__dict__, **(extra or {})},
                id=response.id,
                checked=False,
            )
        except DeviceNotRegisteredError:
            # Mark the push token as inactive
            logger.info("Device no longer registered: %s", device.expo_token)
            device.delete()
            return
        except PushTicketError as exc:
            # Encountered some other per-notification error.
            logger.error(
                "PushTicketError for token=%s, message=%s, extra=%s, response=%s",
                device.expo_token,
                title,
                extra,
                exc.push_response._asdict(),
            )
            raise
        except Exception:
            # Encountered some other error.
            logger.exception(
                "Unexpected error for token=%s, message=%s, extra=%s",
                device.expo_token,
                title,
                extra,
            )
            raise


def check_receipts(responses: Iterable[PushMessage]):
    client = _build_push_client()
    try:
        receipts = client.check_receipts(responses)
        logger.debug("Received %d receipts", len(receipts))
        if not receipts:
            return []
        errors = [receipt for receipt in receipts if receipt.status != "ok"]
        for error in errors:
            logger.error("Receipt error: %s", error)
        logger.warning("Failing percentage: %.2f%%", 100 * len(errors) / len(receipts))
        return errors
    except PushServerError as exc:
        # Encountered some other per-notification error.
        logger.error(
            "PushServerError in check_receipts: errors=%s, response_data=%s",
            exc.errors,
            exc.response_data,
        )
        raise
    except Exception as exc:
        logger.exception("Unexpected error in check_receipts: %s", exc)
        raise
