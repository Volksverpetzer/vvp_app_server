"""Contains the views for the payment functionality."""

import os

import stripe
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def paymentIntent(request: HttpRequest):
    """Create a Payment Intent.

    Args:
        request : GET Request

    Returns:
       JsonResponse: client_secret and amount
    """
    web = request.GET.get("web")
    amount = request.GET.get("amount")
    if amount is None or amount not in ["3", "5", "10", "25", "50", "100"]:
        amount = 500
    else:
        amount = int(amount) * 100
    # get stripe secret key from environment variable
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    if web:
        stripe.ApplePayDomain.create(
            domain_name="volksverpetzer.de",
        )
    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency="eur",
    )
    client_secret = intent.client_secret
    return JsonResponse({"client_secret": client_secret, "amount": amount})


@csrf_exempt
def createSubscription(request: HttpRequest):
    """Create a Subscription.

    Args:
        request : POST Request

    Returns:
        JsonResponse: subscription
    """
    amount = request.POST.get("amount")
    customer = request.POST.get("customer")
    if customer is None:
        return JsonResponse({"error": "Customer is required"}, status=400)
    price_id = "price_1NZZDUFricedKvSmfqgZOYKj"
    if amount is None or amount not in ["3", "5", "10", "25", "50", "100"]:
        amount = 500
    else:
        amount = int(amount) * 100
    # get stripe secret key from environment variable
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    subscription = stripe.Subscription.create(
        customer=customer,
        items=[{"price": price_id}],
    )
    return JsonResponse({"subscription": subscription})
