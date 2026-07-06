import json
import os
import time
from typing import Any
from unittest.mock import MagicMock, patch

import requests

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import NotificationDevice, PushMessageLog

example_post = {
    "post_id": 1234,
    "post": {
        "ID": 1,
        "post_author": "1",
        "post_date": "2018-11-06 14:19:18",
        "post_date_gmt": "2018-11-06 14:19:18",
        "post_content": "Welcome to WordPress. This is your first post. Edit or delete it, then start writing!",
        "post_title": "Test Notification!",
        "post_excerpt": "Test Notification successful",
        "post_status": "publish",
        "comment_status": "open",
        "ping_status": "open",
        "post_password": "",
        "post_name": "lokfuehrer-raus",
        "to_ping": "",
        "pinged": "",
        "post_modified": "2018-11-06 14:19:18",
        "post_modified_gmt": "2018-11-06 14:19:18",
        "post_content_filtered": "",
        "post_parent": 0,
        "guid": r"https:\/\/mydomain.dev\/?p=1",
        "menu_order": 0,
        "post_type": "post",
        "post_mime_type": "",
        "comment_count": "1",
        "filter": "raw",
    },
    "post_meta": {
        "key_0": ["0.00"],
        "key_1": ["0"],
        "key_2": ["1"],
        "key_3": ["148724528:1"],
        "key_4": ["10.00"],
        "key_5": ["a:0:{}"],
    },
    "post_thumbnail": r"https:\/\/mydomain.com\/images\/image.jpg",
    "post_permalink": r"https:\/\/www.volksverpetzer.de\/social-media\/lokfuehrer-raus\/",
    "taxonomies": {
        "category": {
            "uncategorized": {
                "term_id": 1,
                "name": "Uncategorized",
                "slug": "uncategorized",
                "term_group": 0,
                "term_taxonomy_id": 1,
                "taxonomy": "category",
                "description": "",
                "parent": 10,
                "count": 7,
                "filter": "raw",
            },
            "secondcat": {
                "term_id": 2,
                "name": "Second Cat",
                "slug": "secondcat",
                "term_group": 0,
                "term_taxonomy_id": 2,
                "taxonomy": "category",
                "description": "",
                "parent": 1,
                "count": 1,
                "filter": "raw",
            },
        }
    },
}

# Create your tests here.


class TestNotification(TestCase):
    # Client instance for requests with CSRF checks
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.c: Client

    def setUp(self):
        self.c = Client(enforce_csrf_checks=True)
        NotificationDevice.objects.create(
            expo_token="ExponentPushToken[WKgPMINOj-poMgtFJAJARh]",
            notification_new_post=True,
        )
        NotificationDevice.objects.create(
            expo_token="ExponentPushToken[t-_fyZOLWP9YfwRhepmL48]",
            notification_new_post=True,
            notification_new_fact_check=True,
        )

    def test_register_token_view(self):
        response = self.c.post(
            "/register",
            {
                "expo_token": "ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]",
                "settings": {
                    "new_post": {"value": False},
                    "new_fact_check": {"value": True},
                },
            },
            content_type="application/json",
        )
        exists = NotificationDevice.objects.filter(
            expo_token="ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]"
        ).exists()
        self.assertEqual(exists, True)
        self.assertEqual(response.status_code, 200)

    def test_send_notification(self):
        mock_post = {"link": "https://www.volksverpetzer.de/test/", "title": {"rendered": "Test"}, "yoast_head_json": {}}
        found_response = MagicMock()
        found_response.json.return_value = [mock_post]
        not_found_response = MagicMock()
        not_found_response.json.return_value = []

        with patch("notifications.services.webhook_new_post.requests.get", side_effect=[found_response, not_found_response]):
            start_time = time.time()
            response = self.c.post(
                "/webhook_new_post",
                data=example_post,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
            )
            self.assertEqual(response.status_code, 200)
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.assertLess(elapsed_time, 3.0)
            missing_post = {**example_post, "post": {**example_post["post"], "post_name": "das-ist-ein-test-hier"}}
            response = self.c.post(
                "/webhook_new_post",
                data=missing_post,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
            )
            self.assertEqual(response.status_code, 503)

    def test_missing_auth_header_returns_403(self):
        response = self.c.post(
            "/webhook_new_post",
            data=example_post,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_malformed_auth_scheme_returns_403(self):
        response = self.c.post(
            "/webhook_new_post",
            data=example_post,
            content_type="application/json",
            HTTP_AUTHORIZATION="Token sometoken",
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_token_returns_403(self):
        response = self.c.post(
            "/webhook_new_post",
            data=example_post,
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        self.assertEqual(response.status_code, 403)

    def test_bearer_scheme_is_case_insensitive(self):
        mock_post = {"link": "https://www.volksverpetzer.de/test/", "title": {"rendered": "Test"}, "yoast_head_json": {}}
        found_response = MagicMock()
        found_response.json.return_value = [mock_post]
        with patch("notifications.services.webhook_new_post.requests.get", return_value=found_response):
            response = self.c.post(
                "/webhook_new_post",
                data=example_post,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'bearer {os.environ["NOTIFICATION_BEARER"]}',
            )
        self.assertEqual(response.status_code, 200)

    def test_missing_notification_bearer_env_returns_403(self):
        env_without_bearer = {k: v for k, v in os.environ.items() if k != "NOTIFICATION_BEARER"}
        with patch.dict(os.environ, env_without_bearer, clear=True):
            response = self.c.post(
                "/webhook_new_post",
                data=example_post,
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer sometoken",
            )
        self.assertEqual(response.status_code, 403)

    def test_invalid_json_body_returns_400(self):
        response = self.c.post(
            "/webhook_new_post",
            data="not-json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid JSON", response.json()["error"])

    def test_non_dict_body_returns_400(self):
        response = self.c.post(
            "/webhook_new_post",
            data=json.dumps([1, 2, 3]),
            content_type="application/json",
            HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
        )
        self.assertEqual(response.status_code, 400)

    def test_wp_api_non2xx_returns_503_upstream_error(self):
        error_response = MagicMock()
        error_response.raise_for_status.side_effect = requests.exceptions.HTTPError("503 Server Error")
        with patch("notifications.services.webhook_new_post.requests.get", return_value=error_response):
            response = self.c.post(
                "/webhook_new_post",
                data=example_post,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Upstream error", response.content)

    def test_missing_post_name_returns_400(self):
        payload = {**example_post, "post": {**example_post["post"]}}
        del payload["post"]["post_name"]
        response = self.c.post(
            "/webhook_new_post",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing post.post_name", response.json()["error"])

    def test_register_accepts_pruefpunkt_setting(self):
        response = self.c.post(
            "/register",
            {
                "expo_token": "ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]",
                "settings": {
                    "new_post": {"value": False},
                    "new_fact_check": {"value": True},
                    "new_pruefpunkt": {"value": True},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        device = NotificationDevice.objects.get(
            expo_token="ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]"
        )
        self.assertTrue(device.notification_new_pruefpunkt)

    def test_register_without_pruefpunkt_keeps_default(self):
        # Older app versions omit new_pruefpunkt; field stays at its default.
        response = self.c.post(
            "/register",
            {
                "expo_token": "ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]",
                "settings": {
                    "new_post": {"value": True},
                    "new_fact_check": {"value": True},
                },
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        device = NotificationDevice.objects.get(
            expo_token="ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]"
        )
        self.assertFalse(device.notification_new_pruefpunkt)

    def test_register_malformed_settings_returns_400(self):
        # Missing new_fact_check and a non-dict new_post: a client-side payload
        # error, so it must be a 400 rather than a masked 500.
        response = self.c.post(
            "/register",
            {
                "expo_token": "ExponentPushToken[4LS0LwHjgUatWcx6H22e0g]",
                "settings": {"new_post": True},
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_pruefpunkt_post_targets_pruefpunkt_devices(self):
        pp_device = NotificationDevice.objects.create(
            expo_token="ExponentPushToken[ppDeviceTokenAAAAAAAA]",
            notification_new_post=False,
            notification_new_fact_check=False,
            notification_new_pruefpunkt=True,
        )
        pp_post = {
            **example_post,
            "post_permalink": "https://www.pruefpunkt.org/some/article/",
        }
        mock_post = {
            "link": "https://www.pruefpunkt.org/some/article/",
            "title": {"rendered": "PP Test"},
            "yoast_head_json": {},
        }
        found_response = MagicMock()
        found_response.json.return_value = [mock_post]
        with patch(
            "notifications.services.webhook_new_post.requests.get",
            return_value=found_response,
        ), patch(
            "notifications.services.webhook_new_post.async_task"
        ) as mock_async:
            response = self.c.post(
                "/webhook_new_post",
                data=pp_post,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_async.called)
        args = mock_async.call_args.args
        devices, heading = args[1], args[2]
        self.assertTrue(heading.startswith("Prüfpunkt"))
        tokens = {d.expo_token for d in devices}
        self.assertIn(pp_device.expo_token, tokens)
        # volksverpetzer devices (pruefpunkt off by default) must be excluded
        self.assertNotIn("ExponentPushToken[WKgPMINOj-poMgtFJAJARh]", tokens)

    def test_volksverpetzer_post_targets_post_devices(self):
        pp_device = NotificationDevice.objects.create(
            expo_token="ExponentPushToken[ppDeviceTokenBBBBBBBB]",
            notification_new_post=False,
            notification_new_fact_check=False,
            notification_new_pruefpunkt=True,
        )
        mock_post = {
            "link": "https://www.volksverpetzer.de/test/",
            "title": {"rendered": "Test"},
            "yoast_head_json": {},
        }
        found_response = MagicMock()
        found_response.json.return_value = [mock_post]
        with patch(
            "notifications.services.webhook_new_post.requests.get",
            return_value=found_response,
        ), patch(
            "notifications.services.webhook_new_post.async_task"
        ) as mock_async:
            response = self.c.post(
                "/webhook_new_post",
                data=example_post,
                content_type="application/json",
                HTTP_AUTHORIZATION=f'Bearer {os.environ["NOTIFICATION_BEARER"]}',
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_async.called)
        args = mock_async.call_args.args
        devices, heading = args[1], args[2]
        self.assertTrue(heading.startswith("Volksverpetzer"))
        tokens = {d.expo_token for d in devices}
        self.assertIn("ExponentPushToken[WKgPMINOj-poMgtFJAJARh]", tokens)
        # pruefpunkt-only device must not get the volksverpetzer post
        self.assertNotIn(pp_device.expo_token, tokens)


class NotificationStatsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.token = os.environ["NOTIFICATION_BEARER"]  # nosec

    def _post(self, payload, token=None):
        return self.client.post(
            "/notification_stats",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token or self.token}",
        )

    def test_missing_auth_returns_403(self):
        response = self.client.post("/notification_stats", content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_wrong_token_returns_403(self):
        response = self.client.post(
            "/notification_stats",
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong-token",  # nosec
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_slug_returns_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_missing_title_returns_400(self):
        response = self._post({"post": {"post_name": "my-post"}})
        self.assertEqual(response.status_code, 400)

    def test_not_delivered_returns_false(self):
        payload = {"post": {"post_name": "my-post", "post_title": "My Post"}}
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"slug": "my-post", "success": False})

    def test_delivered_returns_true(self):
        device = NotificationDevice.objects.create(expo_token="ExponentPushToken[stats-test]")
        PushMessageLog.objects.create(
            id="stats-log-1", to=device, body="My Post", title="My Post", data={}
        )
        payload = {"post": {"post_name": "my-post", "post_title": "My Post"}}
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"slug": "my-post", "success": True})

    def test_get_returns_405(self):
        response = self.client.get(
            "/notification_stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 405)

    def test_non_dict_body_returns_400(self):
        response = self.client.post(
            "/notification_stats",
            data=json.dumps(["not", "a", "dict"]),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("payload must be a JSON object", response.json()["error"])

    def test_bearer_scheme_is_case_insensitive(self):
        response = self.client.post(
            "/notification_stats",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing slug", response.json()["error"])

    def test_delivered_by_url_returns_true(self):
        device = NotificationDevice.objects.create(expo_token="ExponentPushToken[stats-url-test]")
        PushMessageLog.objects.create(
            id="stats-url-log-1",
            to=device,
            body="My Post",
            title="My Post",
            data={"url": "https://www.volksverpetzer.de/test/"},
        )
        payload = {
            "post": {
                "post_name": "my-post",
                "post_title": "My Post",
                "link": "https://www.volksverpetzer.de/test/",
            }
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"slug": "my-post", "success": True})

    def test_url_query_falls_back_to_body_for_legacy_rows(self):
        device = NotificationDevice.objects.create(expo_token="ExponentPushToken[stats-legacy-test]")
        PushMessageLog.objects.create(
            id="stats-legacy-log-1",
            to=device,
            body="My Post",
            title="My Post",
            data={},
        )
        payload = {
            "post": {
                "post_name": "my-post",
                "post_title": "My Post",
                "link": "https://www.volksverpetzer.de/test/",
            }
        }
        response = self._post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"slug": "my-post", "success": True})


class RegisterErrorsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            "/register",
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid JSON", response.json()["error"])

    def test_missing_expo_token_field_returns_400(self):
        response = self.client.post(
            "/register",
            data=json.dumps({"settings": {}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing field", response.json()["error"])

    def test_invalid_expo_token_returns_403(self):
        response = self.client.post(
            "/register",
            data=json.dumps({
                "expo_token": "not-a-valid-token",
                "settings": {"new_post": {"value": True}, "new_fact_check": {"value": False}},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("invalid expo token", response.json()["error"])

    @patch("notifications.services.register.NotificationDevice.objects.get_or_create")
    def test_db_error_returns_500(self, mock_goc):
        mock_goc.side_effect = Exception("db error")
        response = self.client.post(
            "/register",
            data=json.dumps({
                "expo_token": "ExponentPushToken[test-token-1234]",
                "settings": {"new_post": {"value": True}, "new_fact_check": {"value": False}},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 500)


class SendPushMessageTest(TestCase):
    def setUp(self):
        self.device = NotificationDevice.objects.create(
            expo_token="ExponentPushToken[send-test-abc]"
        )

    @patch("notifications.helper._build_push_client")
    def test_duplicate_messages_are_skipped(self, mock_build):
        PushMessageLog.objects.create(
            id="log-dup-1", to=self.device, body="body", title="title", data={}
        )
        send_mock = mock_build.return_value
        from notifications.helper import send_push_message
        send_push_message([self.device], "title", "body")
        send_mock.publish_multiple.assert_not_called()

    @patch("notifications.helper.PushMessageLog.objects.create")
    @patch("notifications.helper._build_push_client")
    def test_successful_send_creates_log(self, mock_build, mock_log_create):
        ticket = MagicMock()
        ticket.id = "ticket-1"
        ticket.validate_response.return_value = None
        mock_build.return_value.publish_multiple.return_value = [ticket]

        from notifications.helper import send_push_message
        send_push_message([self.device], "title", "body")

        mock_log_create.assert_called_once()

    @patch("notifications.helper._build_push_client")
    def test_device_not_registered_deletes_device(self, mock_build):
        from exponent_server_sdk import DeviceNotRegisteredError
        from notifications.helper import send_push_message

        ticket = MagicMock()
        ticket.validate_response.side_effect = DeviceNotRegisteredError(
            MagicMock(errors=[], status="error", message="NotRegistered", details={})
        )
        mock_build.return_value.publish_multiple.return_value = [ticket]

        send_push_message([self.device], "title", "new-body")
        self.assertFalse(
            NotificationDevice.objects.filter(pk=self.device.pk).exists()
        )

    @patch("notifications.helper.time.sleep")
    @patch("notifications.helper.send_push_message")
    def test_send_push_message_delayed_calls_send_then_sleeps(self, mock_send, mock_sleep):
        from notifications.helper import send_push_message_delayed
        send_push_message_delayed([self.device], "t", "b", extra={"url": "x"})
        mock_send.assert_called_once_with([self.device], "t", "b", {"url": "x"})
        mock_sleep.assert_called_once_with(15)

    @patch.dict(os.environ, {"EXPO_TOKEN": "test-expo-token"})  # nosec
    def test_build_push_client_with_token(self):
        from notifications.helper import _build_push_client
        client = _build_push_client()
        self.assertIsNotNone(client)

    @patch("notifications.helper._build_push_client")
    def test_push_server_error_is_reraised(self, mock_build):
        from exponent_server_sdk import PushServerError
        mock_build.return_value.publish_multiple.side_effect = PushServerError(
            MagicMock(), MagicMock(), errors=[], response_data={}
        )
        from notifications.helper import send_push_message
        with self.assertRaises(PushServerError):
            send_push_message([self.device], "title", "body2")

    @patch("notifications.helper._build_push_client")
    def test_connection_error_is_reraised(self, mock_build):
        from requests.exceptions import ConnectionError as ReqConnectionError
        mock_build.return_value.publish_multiple.side_effect = ReqConnectionError()
        from notifications.helper import send_push_message
        with self.assertRaises(ReqConnectionError):
            send_push_message([self.device], "title", "body3")


class CheckReceiptsTest(TestCase):
    def setUp(self):
        self.device = NotificationDevice.objects.create(
            expo_token="ExponentPushToken[receipts-test]"
        )

    @patch("notifications.helper._build_push_client")
    def test_check_receipts_returns_errors(self, mock_build):
        ok = MagicMock(status="ok")
        err = MagicMock(status="error")
        mock_build.return_value.check_receipts.return_value = [ok, err]
        from notifications.helper import check_receipts
        errors = check_receipts([])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].status, "error")

    @patch("notifications.helper._build_push_client")
    def test_check_receipts_empty_returns_empty_list(self, mock_build):
        mock_build.return_value.check_receipts.return_value = []
        from notifications.helper import check_receipts
        errors = check_receipts([])
        self.assertEqual(errors, [])

    @patch("notifications.helper._build_push_client")
    def test_check_receipts_push_server_error_reraised(self, mock_build):
        from exponent_server_sdk import PushServerError
        mock_build.return_value.check_receipts.side_effect = PushServerError(
            MagicMock(), MagicMock(), errors=[], response_data={}
        )
        from notifications.helper import check_receipts
        with self.assertRaises(PushServerError):
            check_receipts([])


class TaskMonitorViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="monitor", password="pw")  # nosec
        self.client = Client()
        self.client.login(username="monitor", password="pw")  # nosec

    @patch("notifications.services.task_monitor.get_broker")
    @patch("notifications.services.task_monitor.Stat")
    def test_task_monitor_renders(self, mock_stat, mock_broker):
        mock_stat.get_all.return_value = []
        response = self.client.get("/task_monitor")
        self.assertEqual(response.status_code, 200)

    def test_task_monitor_redirects_unauthenticated(self):
        self.client.logout()
        response = self.client.get("/task_monitor")
        self.assertEqual(response.status_code, 302)


class ReceiptsMonitorViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="receipts", password="pw")  # nosec
        self.client = Client()
        self.client.login(username="receipts", password="pw")  # nosec

    @patch("notifications.services.receipts_monitor.check_receipts", return_value=[])
    def test_receipts_monitor_renders(self, _mock):
        response = self.client.get("/receipts_monitor")
        self.assertEqual(response.status_code, 200)

    def test_receipts_monitor_redirects_unauthenticated(self):
        self.client.logout()
        response = self.client.get("/receipts_monitor")
        self.assertEqual(response.status_code, 302)
