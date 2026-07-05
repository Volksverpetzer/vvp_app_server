import json
import os
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, override_settings

from .models import ContactRequest

ASANA_ENV = {"ASANA_TOKEN": "token", "ASANA_PROJECT_GID": "12345"}


def asana_response(status_code: int = 201) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = ""
    return response


@override_settings(RATELIMIT_ENABLE=False)
class ContactTests(TestCase):
    def setUp(self):
        self.c = Client(enforce_csrf_checks=True)

    def post(self, body: dict):
        return self.c.post("/contact", body, content_type="application/json")

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_send_feedback(self, mock_post: MagicMock):
        response = self.post(
            {
                "category": "app_feedback",
                "title": "Dark mode",
                "message": "Die App ist super, aber der Dark Mode ist zu hell.",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertTrue(ContactRequest.objects.filter(title="Dark mode").exists())
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]["data"]
        self.assertEqual(payload["name"], "App-Feedback | Dark mode")
        self.assertEqual(payload["projects"], ["12345"])

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_send_fake_report(self, mock_post: MagicMock):
        response = self.post(
            {
                "category": "report_fake",
                "title": "https://welt.de/fake",
                "message": "Das ist ein Fake.",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_fake_report_requires_url_title(self, mock_post: MagicMock):
        response = self.post(
            {
                "category": "report_fake",
                "title": "kein link",
                "message": "Das ist ein Fake.",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content)["success"])
        mock_post.assert_not_called()

    def test_invalid_category(self):
        response = self.post(
            {"category": "spam", "title": "t", "message": "m"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ContactRequest.objects.exists())

    def test_missing_title(self):
        response = self.post({"category": "other", "message": "m"})
        self.assertEqual(response.status_code, 400)

    def test_missing_message(self):
        response = self.post({"category": "other", "title": "t"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_json(self):
        response = self.c.post(
            "/contact", "not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_asana_env_returns_failure(self):
        response = self.post(
            {"category": "other", "title": "t", "message": "eine Nachricht"}
        )
        self.assertEqual(response.status_code, 502)
        self.assertFalse(json.loads(response.content)["success"])

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response(403))
    def test_asana_error_returns_failure(self, mock_post: MagicMock):
        response = self.post(
            {"category": "other", "title": "t", "message": "eine Nachricht"}
        )
        self.assertEqual(response.status_code, 502)

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_duplicate_request_is_not_resubmitted(self, mock_post: MagicMock):
        body = {"category": "other", "title": "t", "message": "eine Nachricht"}
        first = json.loads(self.post(body).content)
        second = json.loads(self.post(body).content)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(ContactRequest.objects.count(), 1)
        mock_post.assert_called_once()
