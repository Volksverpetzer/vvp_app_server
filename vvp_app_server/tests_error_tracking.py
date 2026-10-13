from unittest.mock import patch

from django.test import SimpleTestCase

from vvp_app_server.error_tracking import init_error_tracking, scrub_event


class ErrorTrackingTest(SimpleTestCase):
    @patch("sentry_sdk.init")
    def test_noop_without_dsn(self, mock_init):
        self.assertFalse(init_error_tracking(None, "1.0"))
        self.assertFalse(init_error_tracking("", "1.0"))
        mock_init.assert_not_called()

    @patch("sentry_sdk.init")
    def test_inits_with_dsn_without_pii(self, mock_init):
        self.assertTrue(init_error_tracking("https://k@gt.example/1", "1.0"))
        kwargs = mock_init.call_args.kwargs
        self.assertEqual(kwargs["release"], "1.0")
        self.assertFalse(kwargs["send_default_pii"])
        self.assertIs(kwargs["before_send"], scrub_event)

    def test_scrub_event_redacts_expo_tokens(self):
        event = {
            "logentry": {"message": "PushServerError for ExponentPushToken[abc-123]"},
            "exception": {"values": [{"value": "bad ExpoPushToken[xyz]"}]},
        }
        out = scrub_event(event, {})
        text = str(out)
        self.assertNotIn("abc-123", text)
        self.assertNotIn("xyz", text)
        self.assertIn("[expo-token]", text)
