from unittest.mock import MagicMock, patch

from django.core.cache import caches
from django.test import TestCase


class FactApiTestCase(TestCase):
    def setUp(self):
        # googleFact caches responses by request path in both cache layers.
        caches["default"].clear()
        caches["persistent"].clear()

    def test_fact_api(self):
        response = self.client.get("/googleFact")
        # check if the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"claims": []})

    # Mock the Google Fact Check API so the test runs offline; the real call
    # made CI flaky whenever it timed out.
    @patch("factApi.services.google_fact.requests.get")
    def test_fact_api_keywords(self, mock_get):
        mock_get.return_value = MagicMock(
            json=MagicMock(
                return_value={
                    "claims": [
                        {
                            "text": "Reviewed claim",
                            "claimReview": [{"reviewDate": "2026-01-01"}],
                        },
                        {"text": "Claim without review"},
                        {
                            "text": "Claim with empty review date",
                            "claimReview": [{"reviewDate": ""}],
                        },
                    ]
                }
            )
        )
        response = self.client.get("/googleFact?keywords=corona,impfung")
        # check if the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args.kwargs["params"]["query"], "corona,impfung")
        # Claims without a review or with an empty review date are dropped.
        claims = response.json()["claims"]
        self.assertEqual([c["text"] for c in claims], ["Reviewed claim"])
