import os
import json
from datetime import datetime, timezone
from flask import Blueprint, redirect, url_for, request, session, flash, current_app
from flask_login import login_required, current_user
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app import db
from models.business import Business

google_oauth_bp = Blueprint('google_oauth', __name__, url_prefix='/google')

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/business.manage',
]

CLIENT_CONFIG = {
    'web': {
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'redirect_uris': [f'{BASE_URL}/google/callback'],
    }
}


def get_flow():
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=f'{BASE_URL}/google/callback',
    )
    return flow


@google_oauth_bp.route('/connect')
@login_required
def connect():
    flow = get_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    session['google_oauth_state'] = state
    return redirect(auth_url)


@google_oauth_bp.route('/callback')
@login_required
def callback():
    state = session.get('google_oauth_state')
    if not state or state != request.args.get('state'):
        flash('OAuth state mismatch. Please try again.', 'danger')
        return redirect(url_for('dashboard.connect'))

    if 'error' in request.args:
        flash(f'Google authorization failed: {request.args["error"]}', 'danger')
        return redirect(url_for('dashboard.connect'))

    flow = get_flow()
    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        current_app.logger.error(f'OAuth token fetch failed: {e}')
        flash('Failed to get Google authorization. Please try again.', 'danger')
        return redirect(url_for('dashboard.connect'))

    credentials = flow.credentials

    # Fetch the list of Google Business locations for this account
    try:
        service = build('mybusinessaccountmanagement', 'v1', credentials=credentials)
        accounts_result = service.accounts().list().execute()
        accounts = accounts_result.get('accounts', [])
    except Exception as e:
        current_app.logger.error(f'Failed to fetch Google Business accounts: {e}')
        flash('Connected to Google, but could not fetch your Business Profile. '
              'Make sure you have a Google Business Profile set up.', 'warning')
        return redirect(url_for('dashboard.index'))

    if not accounts:
        flash('No Google Business accounts found on this Google account.', 'warning')
        return redirect(url_for('dashboard.connect'))

    locations_added = 0
    for account in accounts:
        account_name = account.get('name')  # e.g. "accounts/123456789"
        try:
            loc_service = build('mybusinessbusinessinformation', 'v1', credentials=credentials)
            locs_result = loc_service.accounts().locations().list(parent=account_name).execute()
            locations = locs_result.get('locations', [])
        except Exception as e:
            current_app.logger.warning(f'Could not list locations for {account_name}: {e}')
            continue

        for loc in locations:
            location_id = loc.get('name')  # e.g. "locations/123"
            business_name = loc.get('title', 'My Business')

            # Upsert: update if already connected, create if new
            existing = Business.query.filter_by(
                user_id=current_user.id,
                google_location_id=location_id
            ).first()

            expiry = None
            if credentials.expiry:
                expiry = credentials.expiry.replace(tzinfo=timezone.utc) if credentials.expiry.tzinfo is None else credentials.expiry

            if existing:
                existing.google_access_token = credentials.token
                existing.google_refresh_token = credentials.refresh_token or existing.google_refresh_token
                existing.token_expiry = expiry
                existing.business_name = business_name
            else:
                biz = Business(
                    user_id=current_user.id,
                    google_location_id=location_id,
                    business_name=business_name,
                    google_access_token=credentials.token,
                    google_refresh_token=credentials.refresh_token,
                    token_expiry=expiry,
                )
                db.session.add(biz)
                locations_added += 1

    db.session.commit()

    if locations_added > 0:
        flash(f'Successfully connected {locations_added} Google Business location(s)!', 'success')
    else:
        flash('Google Business Profile updated successfully.', 'success')

    return redirect(url_for('dashboard.index'))
