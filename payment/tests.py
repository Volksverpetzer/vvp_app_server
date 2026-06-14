import os
from unittest import mock

from django.test import Client, RequestFactory, TestCase

# Create your tests here.
# Django test case


class PaymentTestCase(TestCase):
    def setUp(self):
        # Initialize the client
        self.client = Client(enforce_csrf_checks=True)

        # Mock the environment variable for Stripe API key
        self.env_patcher = mock.patch.dict(
            os.environ, {"STRIPE_SECRET_KEY": "mock_stripe_key"}
        )  # nosec
        self.env_patcher.start()

        # Set up the mock for stripe.PaymentIntent.create
        self.stripe_payment_intent_patcher = mock.patch("stripe.PaymentIntent.create")
        self.mock_payment_intent = self.stripe_payment_intent_patcher.start()

        # Set up the mock for stripe.ApplePayDomain.create
        self.stripe_apple_pay_patcher = mock.patch("stripe.ApplePayDomain.create")
        self.mock_apple_pay = self.stripe_apple_pay_patcher.start()

        # Configure the mock to return a predefined response
        self.mock_payment_intent.return_value = mock.MagicMock(
            client_secret="mock_client_secret"
        )

    def tearDown(self):
        # Stop all the patchers
        self.stripe_payment_intent_patcher.stop()
        self.stripe_apple_pay_patcher.stop()
        self.env_patcher.stop()

    def test_payment(self):
        response = self.client.post("/paymentIntent")
        # check if the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue("client_secret" in data)
        self.assertEqual(data["amount"], 500)

        # Verify the mock was called with the expected arguments
        self.mock_payment_intent.assert_called_with(amount=500, currency="eur")

        # Reset the mock for the next test
        self.mock_payment_intent.reset_mock()

        response = self.client.post("/paymentIntent?amount=3")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue("client_secret" in data)
        self.assertEqual(data["amount"], 300)

        # Verify the mock was called with the expected arguments for amount=3
        self.mock_payment_intent.assert_called_with(amount=300, currency="eur")

    def test_malicious_payment(self):
        # Test with extremely large amount
        response = self.client.post("/paymentIntent?amount=100000")
        data = response.json()
        self.assertTrue("client_secret" in data)
        self.assertEqual(data["amount"], 500)  # Should default to 500

        # Verify the mock was called with the default amount
        self.mock_payment_intent.assert_called_with(amount=500, currency="eur")

        # Reset the mock for the next test
        self.mock_payment_intent.reset_mock()

        # Test with negative amount
        response = self.client.post("/paymentIntent?amount=-5")
        data = response.json()
        self.assertTrue("client_secret" in data)
        self.assertEqual(data["amount"], 500)  # Should default to 500

        # Verify the mock was called with the default amount
        self.mock_payment_intent.assert_called_with(amount=500, currency="eur")

    def test_web_payment(self):
        # Test with web parameter
        response = self.client.post("/paymentIntent?web=true")
        data = response.json()
        self.assertTrue("client_secret" in data)
        self.assertEqual(data["amount"], 500)

        # Verify ApplePayDomain.create was called
        self.mock_apple_pay.assert_called_with(domain_name="volksverpetzer.de")

        # Verify PaymentIntent.create was called
        self.mock_payment_intent.assert_called_with(amount=500, currency="eur")


class CreateSubscriptionTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.env_patcher = mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "mock_key"})  # nosec
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def _call(self, data):
        from payment.views import createSubscription
        request = self.factory.post("/createSubscription", data)
        return createSubscription(request)

    def test_missing_customer_returns_400(self):
        response = self._call({})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Customer is required", response.content.decode())

    @mock.patch("stripe.Subscription.create")
    def test_valid_request_returns_subscription(self, mock_sub):
        mock_sub.return_value = {"id": "sub_123", "status": "active"}
        response = self._call({"customer": "cus_123", "amount": "10"})
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertIn("subscription", data)
        mock_sub.assert_called_once()

    @mock.patch("stripe.Subscription.create")
    def test_invalid_amount_uses_fixed_price_id(self, mock_sub):
        mock_sub.return_value = {"id": "sub_456"}
        self._call({"customer": "cus_456", "amount": "999"})
        call_kwargs = mock_sub.call_args[1]
        self.assertEqual(call_kwargs["items"][0]["price"], "price_1NZZDUFricedKvSmfqgZOYKj")
