import json
import os
from unittest.mock import MagicMock, patch

from django.db import IntegrityError, transaction
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
    def test_app_metadata_is_stored_and_in_notes(self, mock_post: MagicMock):
        response = self.post(
            {
                "category": "app_feedback",
                "title": "Dark mode",
                "message": "Der Dark Mode ist zu hell.",
                "app_variant": "Volksverpetzer",
                "app_version": "2.3.0",
                "platform": "ios",
            }
        )
        self.assertEqual(response.status_code, 200)
        request = ContactRequest.objects.get(title="Dark mode")
        self.assertEqual(request.app_variant, "Volksverpetzer")
        self.assertEqual(request.app_version, "2.3.0")
        self.assertEqual(request.platform, "ios")
        notes = mock_post.call_args.kwargs["json"]["data"]["notes"]
        self.assertIn("App: Volksverpetzer | 2.3.0 | ios", notes)

    @patch.dict(
        os.environ, ASANA_ENV | {"ASANA_SECTION_APP_FEEDBACK": "777"}
    )
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_category_section_is_used_when_configured(self, mock_post: MagicMock):
        response = self.post(
            {
                "category": "app_feedback",
                "title": "Dark mode",
                "message": "Der Dark Mode ist zu hell.",
            }
        )
        self.assertEqual(response.status_code, 200)
        payload = mock_post.call_args.kwargs["json"]["data"]
        self.assertEqual(
            payload["memberships"], [{"project": "12345", "section": "777"}]
        )

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_long_title_is_truncated_consistently(self, mock_post: MagicMock):
        response = self.post(
            {
                "category": "other",
                "title": "x" * 600,
                "message": "eine Nachricht",
            }
        )
        self.assertEqual(response.status_code, 200)
        stored_title = ContactRequest.objects.get().title
        self.assertEqual(len(stored_title), 500)
        payload = mock_post.call_args.kwargs["json"]["data"]
        self.assertEqual(payload["name"], f"Sonstiges | {stored_title}")

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

    def test_non_object_json_is_rejected(self):
        for body in ('"a string"', "[1, 2]", "42", "null"):
            response = self.c.post(
                "/contact", body, content_type="application/json"
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
        # The row is kept unposted so a retry reattempts the Asana post
        self.assertFalse(ContactRequest.objects.get().posted_to_asana)

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post")
    def test_retry_after_asana_failure_posts_again(self, mock_post: MagicMock):
        body = {"category": "other", "title": "t", "message": "eine Nachricht"}
        mock_post.return_value = asana_response(500)
        self.assertEqual(self.post(body).status_code, 502)
        mock_post.return_value = asana_response()
        response = self.post(body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])
        self.assertEqual(mock_post.call_count, 2)

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_duplicate_request_is_not_resubmitted(self, mock_post: MagicMock):
        body = {"category": "other", "title": "t", "message": "eine Nachricht"}
        first = json.loads(self.post(body).content)
        second = json.loads(self.post(body).content)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(ContactRequest.objects.count(), 1)
        mock_post.assert_called_once()

    @patch.dict(os.environ, ASANA_ENV)
    @patch("contact.asana.requests.post", return_value=asana_response())
    def test_dedupe_hit_on_unposted_row_reattempts_post(
        self, mock_post: MagicMock
    ):
        # Simulates the concurrent-duplicate race: the row exists but the
        # Asana task was never created. The duplicate must not report
        # success without posting.
        fields = {
            "category": "other",
            "title": "t",
            "message": "eine Nachricht",
            "app_variant": "",
            "app_version": "",
            "platform": "",
        }
        ContactRequest.objects.create(
            dedupe_hash=ContactRequest.build_dedupe_hash(**fields), **fields
        )
        response = self.post(
            {"category": "other", "title": "t", "message": "eine Nachricht"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["success"])
        mock_post.assert_called_once()
        self.assertTrue(ContactRequest.objects.get().posted_to_asana)

    def test_dedupe_hash_is_not_ambiguous(self):
        # With a naive delimiter-joined serialization these two payloads
        # would collapse to the same canonical string.
        first = ContactRequest.build_dedupe_hash(
            message="m\x1fplatform=p", platform=""
        )
        second = ContactRequest.build_dedupe_hash(
            message="m", platform="p\x1fplatform="
        )
        self.assertNotEqual(first, second)

    def test_dedupe_is_enforced_at_the_database_level(self):
        # Concurrent identical POSTs may both pass an application-level
        # existence check; the unique hash column collapses them.
        fields = {
            "category": "other",
            "title": "t",
            "message": "m",
            "app_variant": "",
            "app_version": "",
            "platform": "",
        }
        dedupe_hash = ContactRequest.build_dedupe_hash(**fields)
        ContactRequest.objects.create(dedupe_hash=dedupe_hash, **fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContactRequest.objects.create(dedupe_hash=dedupe_hash, **fields)
