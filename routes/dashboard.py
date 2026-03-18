import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.business import Business, ReviewLog

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_MONTHLY_PRICE_ID = os.environ.get('STRIPE_MONTHLY_PRICE_ID', '')


@dashboard_bp.route('/')
@login_required
def index():
    businesses = Business.query.filter_by(user_id=current_user.id).all()

    # Stats for each business
    business_data = []
    for biz in businesses:
        recent_reviews = (
            ReviewLog.query
            .filter_by(business_id=biz.id)
            .order_by(ReviewLog.id.desc())
            .limit(10)
            .all()
        )
        business_data.append({
            'business': biz,
            'recent_reviews': recent_reviews,
        })

    return render_template(
        'dashboard/index.html',
        business_data=business_data,
        stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
        stripe_price_id=STRIPE_MONTHLY_PRICE_ID,
    )


@dashboard_bp.route('/connect')
@login_required
def connect():
    return render_template('dashboard/connect.html')


@dashboard_bp.route('/business/<int:business_id>/toggle-auto-reply', methods=['POST'])
@login_required
def toggle_auto_reply(business_id):
    biz = Business.query.filter_by(id=business_id, user_id=current_user.id).first_or_404()
    biz.auto_reply_enabled = not biz.auto_reply_enabled
    db.session.commit()
    status = 'enabled' if biz.auto_reply_enabled else 'paused'
    flash(f'Auto-reply {status} for {biz.business_name}.', 'success')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/business/<int:business_id>/tone', methods=['POST'])
@login_required
def update_tone(business_id):
    biz = Business.query.filter_by(id=business_id, user_id=current_user.id).first_or_404()
    tone = request.form.get('tone')
    if tone in ('professional', 'friendly', 'formal'):
        biz.reply_tone = tone
        db.session.commit()
        flash(f'Tone updated to {tone}.', 'success')
    else:
        flash('Invalid tone selection.', 'danger')
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/business/<int:business_id>/disconnect', methods=['POST'])
@login_required
def disconnect_business(business_id):
    biz = Business.query.filter_by(id=business_id, user_id=current_user.id).first_or_404()
    name = biz.business_name
    db.session.delete(biz)
    db.session.commit()
    flash(f'{name} has been disconnected.', 'info')
    return redirect(url_for('dashboard.index'))
