import json
import os
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase, override_settings

from .models import FakeReport

# Create your tests here.


class Notification(TestCase):
    c = None

    def setUp(self):
        self.c = Client(enforce_csrf_checks=True)

    @override_settings(RATELIMIT_ENABLE=False)
    def test_send_report(self):
        response = self.c.post(
            "/reportFake",
            {
                "description": "Fake Report",
                "url": "https://welt.de",
                "more_info": "More Infos about KKR:",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeReport.objects.filter(url="https://welt.de").exists(), True)

    @override_settings(RATELIMIT_ENABLE=False)
    def test_send_report_invalid_url_scheme(self):
        response = self.c.post(
            "/reportFake",
            {"description": "d", "url": "javascript:alert(1)", "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertFalse(FakeReport.objects.filter(url="javascript:alert(1)").exists())

    @override_settings(RATELIMIT_ENABLE=False)
    def test_send_report_non_http_url(self):
        response = self.c.post(
            "/reportFake",
            {"description": "d", "url": "welt.de", "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["success"])

    @override_settings(RATELIMIT_ENABLE=False)
    def test_send_report_non_string_url(self):
        response = self.c.post(
            "/reportFake",
            {"description": "d", "url": 42, "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["success"])

    @override_settings(RATELIMIT_ENABLE=False)
    def test_send_report_missing_url_is_rejected(self):
        response = self.c.post(
            "/reportFake",
            {"description": "d", "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["success"])

    @override_settings(RATELIMIT_ENABLE=False)
    @patch.dict(os.environ, {}, clear=True)
    def test_send_report_missing_mailgun_env_returns_failure(self):
        response = self.c.post(
            "/reportFake",
            {"description": "d", "url": "https://example.com", "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["success"])

    @override_settings(RATELIMIT_ENABLE=False)
    @patch.dict(os.environ, {"MAILGUN_TOKEN": "t", "MAILGUN_DOMAIN": "d.com", "MAILGUN_RECEIVER": "r@r.com"})
    @patch("reportFake.views.requests.post")
    def test_send_report_mailgun_non_200_returns_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        response = self.c.post(
            "/reportFake",
            {"description": "d", "url": "https://example.com/unique1", "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["success"])

    @override_settings(RATELIMIT_ENABLE=False)
    def test_send_report_uppercase_scheme_accepted(self):
        response = self.c.post(
            "/reportFake",
            {"description": "d", "url": "HTTPS://welt.de", "more_info": "m"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(FakeReport.objects.filter(url="HTTPS://welt.de").exists())


class ReportFakeViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", password="dummy_password") # nosec
        self.client = Client()
        self.client.login(username="test", password="dummy_password") # nosec

    def test_triageFake_shows_reports(self):
        FakeReport.objects.create(description="d", url="u", more_info="m")
        response = self.client.get("/triageFake")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "d")

    def test_triageFake_javascript_url_rendered_as_text_not_link(self):
        FakeReport.objects.create(
            description="xss", url="javascript:alert(1)", more_info="m", allowed_public=True
        )
        response = self.client.get("/triageFake")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('href="javascript:alert(1)"', content)
        self.assertIn("javascript:alert(1)", content)

    def test_assign_bluesky_rejects_invalid_scheme(self):
        report = FakeReport.objects.create(
            description="d", url="https://example.com", more_info="m", allowed_public=True
        )
        response = self.client.post(
            "/assign-bluesky",
            {"report_id": str(report.id), "bluesky_url": "javascript:void(0)"},
        )
        self.assertRedirects(response, "/triageFake", fetch_redirect_response=False)

    def test_statusFake(self):
        response = self.client.get("/statusFake/999")
        self.assertEqual(response.status_code, 404)
        report = FakeReport.objects.create(
            description="d", url="u", more_info="m", post_id="abc"
        )
        with patch.dict(os.environ, {"BSKY_BOT_HANDLE": "bot.example.com"}):
            response = self.client.get(f"/statusFake/{report.id}")
        data = json.loads(response.content)
        self.assertEqual(data["status"], "posted")
        self.assertEqual(
            data["url"], "https://bsky.app/profile/bot.example.com/post/abc"
        )

    def test_statusFake_url_none_when_bot_handle_missing(self):
        report = FakeReport.objects.create(
            description="d", url="u", more_info="m", post_id="abc"
        )
        env = {k: v for k, v in os.environ.items() if k != "BSKY_BOT_HANDLE"}
        with patch.dict(os.environ, env, clear=True):
            response = self.client.get(f"/statusFake/{report.id}")
        data = json.loads(response.content)
        self.assertEqual(data["status"], "posted")
        self.assertIsNone(data["url"])

    def test_archiveFake_post_archives_report(self):
        report = FakeReport.objects.create(
            description="d", url="https://example.com", more_info="m", allowed_public=True
        )
        response = self.client.post("/archiveFake", {"report_id": str(report.id)})
        self.assertRedirects(response, "/triageFake", fetch_redirect_response=False)
        report.refresh_from_db()
        self.assertFalse(report.allowed_public)

    def test_archiveFake_get_redirects(self):
        response = self.client.get("/archiveFake")
        self.assertRedirects(response, "/triageFake", fetch_redirect_response=False)

    def test_statusFake_pending(self):
        report = FakeReport.objects.create(description="d", url="https://example.com", more_info="m")
        response = self.client.get(f"/statusFake/{report.id}")
        self.assertEqual(response.json()["status"], "pending")
        self.assertIsNone(response.json()["url"])

    def test_statusFake_not_found_with_valid_uuid(self):
        response = self.client.get(f"/statusFake/{uuid.uuid4()}")
        self.assertEqual(response.status_code, 404)

    def test_assign_bluesky_missing_fields_redirects(self):
        response = self.client.post("/assign-bluesky", {"report_id": "", "bluesky_url": ""})
        self.assertRedirects(response, "/triageFake", fetch_redirect_response=False)

    def test_assign_bluesky_valid_post_redirects(self):
        report = FakeReport.objects.create(
            description="d", url="https://example.com", more_info="m", allowed_public=True
        )
        response = self.client.post(
            "/assign-bluesky",
            {"report_id": str(report.id), "bluesky_url": "https://bsky.app/profile/test/post/1"},
        )
        self.assertRedirects(response, "/triageFake", fetch_redirect_response=False)

    def test_ratelimit_view_returns_429(self):
        from reportFake.views import ratelimit_view
        request = RequestFactory().get("/")
        response = ratelimit_view(request, Exception("rate limited"))
        self.assertEqual(response.status_code, 429)

