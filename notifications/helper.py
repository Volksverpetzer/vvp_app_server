import logging
import os
import time
from datetime import timedelta
from typing import Iterable

import requests
from exponent_server_sdk import (  # type: ignore[reportUnknownParameterType]
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushReceipt,
    PushServerError,
    PushTicketError,
)
from django.utils import timezone
from requests.exceptions import ConnectionError, HTTPError

from .models import NotificationDevice, PushMessageLog

logger = logging.getLogger(__name__)


class ImagePushMessage(PushMessage):
    """PushMessage that also sets Expo's `richContent.image` field.

    exponent_server_sdk 2.2.0 doesn't expose richContent yet, so this
    overrides get_payload as the SDK's own docstring recommends for
    fields it hasn't caught up with upstream.
    """

    def __new__(cls, *args, image: str | None = None, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        self.image = image
        return self

    def get_payload(self):
        payload = super().get_payload()
        if self.image:
            payload["richContent"] = {"image": self.image}
        return payload


def _build_push_client() -> PushClient:
    expo_token = os.getenv("EXPO_PUSH_ACCESS_TOKEN")
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
    devices: list[NotificationDevice],
    title: str,
    body: str,
    extra: dict | None = None,
    image: str | None = None,
    channel_id: str | None = None,
):
    """Excetute send_push_message but wait 15 seconds."""
    send_push_message(devices, title, body, extra, image=image, channel_id=channel_id)
    time.sleep(15)


def send_push_message(
    devices: list[NotificationDevice],
    title: str,
    body: str,
    extra: dict | None = None,
    image: str | None = None,
    channel_id: str | None = None,
):
    # `channel_id` is the Android notification channel the app created for this
    # push type (new_post / new_fact_check / new_pruefpunkt). Without it Android
    # files the push under a generic "Miscellaneous" channel.
    # Filter out devices that already have a push message with the same title
    devices_to_notify = []
    mismatched_prior_images: set[str | None] = set()
    skipped_count = 0
    for device in devices:
        # Check if a push log with the same title already exists for this device
        prior_log = (
            PushMessageLog.objects.filter(to=device, body=body, title=title)
            .order_by("-date", "-id")
            .first()
        )
        if prior_log is None:
            devices_to_notify.append(device)
        else:
            skipped_count += 1
            prior_data = prior_log.data if isinstance(prior_log.data, dict) else {}
            prior_image = prior_data.get("image")
            if prior_image != image:
                mismatched_prior_images.add(prior_image)

    if mismatched_prior_images:
        logger.warning(
            "send_push_message: skipped re-fire for title=%s body=%s "
            "(%d device(s) already notified) — new image=%s differs from "
            "previously sent image(s)=%s; those devices will NOT be resent",
            title,
            body,
            skipped_count,
            image,
            mismatched_prior_images,
        )

    # If no devices to notify, return early
    if not devices_to_notify:
        if not mismatched_prior_images:
            logger.info("No new devices to notify with title=%s", title)
        return

    logger.info(
        "send_push_message: sending title=%s body=%s image=%s to %d device(s)",
        title,
        body,
        image,
        len(devices_to_notify),
    )
    client = _build_push_client()
    try:
        responses = client.publish_multiple(
            [
                ImagePushMessage(  # type: ignore[reportUnknownParameterType]
                    to=device.expo_token,
                    body=body,
                    title=title,
                    data=extra,
                    image=image,
                    channel_id=channel_id,
                )
                for device in devices_to_notify
            ]
        )
    except PushServerError as exc:
        # Encountered some likely formatting/validation error.
        logger.error(
            "PushServerError for tokens=%s, message=%s, extra=%s, "
            "errors=%s, response_data=%s",
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
                data={"ticket": response.__dict__, **(extra or {}), "image": image},
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
        # check_receipts_multiple, not check_receipts: the latter posts with a
        # bare requests.post, bypassing the client's session and with it the
        # Authorization header that enhanced push security requires.
        receipts = client.check_receipts_multiple(list(responses))
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


# Expo needs a few minutes to produce receipts and keeps them for about a day,
# so only messages in that window are checked. Messages without a receipt yet
# stay unchecked and are picked up by the next run.
RECEIPT_MIN_AGE = timedelta(minutes=15)
RECEIPT_MAX_AGE = timedelta(days=1)


def process_receipts() -> int:
    """Check pending push receipts and delete devices Expo reports as
    DeviceNotRegistered (app uninstalled, token invalidated).

    Runs on an hourly django-q schedule (migration 0008). A device that is
    still in use re-registers on its next app launch, so deleting one is safe.

    Returns:
        int: number of deleted devices
    """
    now = timezone.now()
    logs = list(
        PushMessageLog.objects.filter(
            checked=False,
            date__lte=now - RECEIPT_MIN_AGE,
            date__gt=now - RECEIPT_MAX_AGE,
        )
    )
    if not logs:
        return 0

    # check_receipts_multiple splits the IDs into requests of 1000, Expo's
    # getReceipts limit, and returns the combined receipts.
    receipts = _build_push_client().check_receipts_multiple(logs)
    device_by_log = {log.id: log.to_id for log in logs}
    unregistered: set[int] = set()
    for receipt in receipts:
        if receipt.is_success():
            continue
        details = receipt.details if isinstance(receipt.details, dict) else {}
        if details.get("error") == PushReceipt.ERROR_DEVICE_NOT_REGISTERED:
            device_id = device_by_log.get(receipt.id)
            if device_id is not None:
                unregistered.add(device_id)
        else:
            logger.error("Receipt error: %s", receipt)

    # Mark before deleting: the delete cascades to the device's log rows.
    PushMessageLog.objects.filter(id__in=[r.id for r in receipts]).update(checked=True)
    NotificationDevice.objects.filter(id__in=unregistered).delete()
    logger.info(
        "process_receipts: %d message(s), %d receipt(s), %d unregistered",
        len(logs),
        len(receipts),
        len(unregistered),
    )
    return len(unregistered)
