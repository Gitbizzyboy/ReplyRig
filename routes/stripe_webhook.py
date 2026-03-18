import os
import stripe
from flask import Blueprint, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app import db
from models.user import User

stripe_bp = Blueprint('stripe', __name__, url_prefix='/stripe')

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
STRIPE_MONTHLY_PRICE_ID = os.environ.get('STRIPE_MONTHLY_PRICE_ID')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')


@stripe_bp.route('/subscribe', methods=['POST'])
@login_required
def create_checkout():
    """Create a Stripe Checkout session and redirect user."""
    try:
        # Create or retrieve Stripe customer
        if current_user.stripe_customer_id:
            customer_id = current_user.stripe_customer_id
        else:
            customer = stripe.Customer.create(email=current_user.email)
            current_user.stripe_customer_id = customer.id
            db.session.commit()
            customer_id = customer.id

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': STRIPE_MONTHLY_PRICE_ID, 'quantity': 1}],
            mode='subscription',
            success_url=f'{BASE_URL}/stripe/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{BASE_URL}/dashboard/',
        )
        return redirect(checkout_session.url, code=303)

    except Exception as e:
        current_app.logger.error(f'Stripe checkout error: {e}')
        flash('Could not start checkout. Please try again.', 'danger')
        return redirect(url_for('dashboard.index'))


@stripe_bp.route('/success')
@login_required
def success():
    flash('🎉 You\'re now on ReplyRig Pro! Auto-replies are live.', 'success')
    return redirect(url_for('dashboard.index'))


@stripe_bp.route('/portal', methods=['POST'])
@login_required
def customer_portal():
    """Redirect to Stripe billing portal for subscription management."""
    if not current_user.stripe_customer_id:
        flash('No billing account found.', 'danger')
        return redirect(url_for('dashboard.index'))

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f'{BASE_URL}/dashboard/',
        )
        return redirect(portal_session.url, code=303)
    except Exception as e:
        current_app.logger.error(f'Stripe portal error: {e}')
        flash('Could not open billing portal. Please try again.', 'danger')
        return redirect(url_for('dashboard.index'))


@stripe_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        current_app.logger.error(f'Stripe webhook error: {e}')
        return jsonify({'error': 'Invalid signature'}), 400

    event_type = event['type']
    data = event['data']['object']

    if event_type == 'checkout.session.completed':
        customer_id = data.get('customer')
        _upgrade_user(customer_id)

    elif event_type in ('customer.subscription.updated', 'invoice.payment_succeeded'):
        customer_id = data.get('customer')
        subscription_status = data.get('status')
        if subscription_status == 'active':
            _upgrade_user(customer_id)

    elif event_type in ('customer.subscription.deleted', 'invoice.payment_failed'):
        customer_id = data.get('customer')
        _downgrade_user(customer_id)

    return jsonify({'received': True}), 200


def _upgrade_user(stripe_customer_id):
    user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if user and user.plan != 'pro':
        user.plan = 'pro'
        db.session.commit()
        current_app.logger.info(f'Upgraded user {user.email} to pro')


def _downgrade_user(stripe_customer_id):
    user = User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    if user and user.plan == 'pro':
        user.plan = 'free'
        db.session.commit()
        current_app.logger.info(f'Downgraded user {user.email} to free')
