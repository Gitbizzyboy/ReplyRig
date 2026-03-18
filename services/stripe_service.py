import os
import stripe
import logging

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
logger = logging.getLogger(__name__)


def get_subscription_status(stripe_customer_id: str) -> dict:
    """
    Fetch current subscription status for a Stripe customer.
    Returns dict with 'active', 'status', 'current_period_end'.
    """
    if not stripe_customer_id:
        return {'active': False, 'status': 'none'}

    try:
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status='all',
            limit=1,
        )
        if not subscriptions.data:
            return {'active': False, 'status': 'none'}

        sub = subscriptions.data[0]
        return {
            'active': sub.status == 'active',
            'status': sub.status,
            'current_period_end': sub.current_period_end,
            'cancel_at_period_end': sub.cancel_at_period_end,
        }

    except stripe.error.StripeError as e:
        logger.error(f'Stripe error fetching subscription: {e}')
        return {'active': False, 'status': 'error'}


def cancel_subscription(stripe_customer_id: str) -> bool:
    """Cancel the customer's active subscription at period end."""
    try:
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status='active',
            limit=1,
        )
        if not subscriptions.data:
            return False

        sub_id = subscriptions.data[0].id
        stripe.Subscription.modify(sub_id, cancel_at_period_end=True)
        return True

    except stripe.error.StripeError as e:
        logger.error(f'Stripe error cancelling subscription: {e}')
        return False
