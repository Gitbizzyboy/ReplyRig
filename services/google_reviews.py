import os
import logging
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app import db
from models.business import Business, ReviewLog

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')


def get_credentials(business: Business) -> Credentials:
    """Build and refresh Google credentials for a business."""
    creds = Credentials(
        token=business.google_access_token,
        refresh_token=business.google_refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        business.google_access_token = creds.token
        if creds.expiry:
            business.token_expiry = creds.expiry.replace(tzinfo=timezone.utc)
        db.session.commit()
        logger.info(f'Refreshed Google token for business {business.id}')

    return creds


def fetch_unanswered_reviews(business: Business) -> list[dict]:
    """
    Fetch reviews from Google My Business that haven't been replied to yet.
    Returns a list of review dicts.
    """
    try:
        creds = get_credentials(business)
        service = build('mybusinessreviews', 'v1', credentials=creds)

        # location_id format: "locations/1234567890"
        location_name = business.google_location_id
        result = service.locations().reviews().list(
            parent=location_name,
            pageSize=50,
        ).execute()

        reviews = result.get('reviews', [])
        unanswered = []

        for review in reviews:
            review_id = review.get('name')  # "locations/.../reviews/..."
            has_reply = bool(review.get('reviewReply'))

            if has_reply:
                # Mark as already replied in our DB if we have a pending record
                existing = ReviewLog.query.filter_by(google_review_id=review_id).first()
                if existing and existing.status == 'pending':
                    existing.status = 'skipped'
                    db.session.commit()
                continue

            # Check if we already processed this review
            existing = ReviewLog.query.filter_by(google_review_id=review_id).first()
            if existing and existing.status in ('replied', 'skipped'):
                continue

            # Parse star rating
            star_map = {
                'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5
            }
            star_str = review.get('starRating', 'FIVE')
            stars = star_map.get(star_str, 5)

            reviewer_name = review.get('reviewer', {}).get('displayName', 'Valued Customer')
            review_text = review.get('comment', '')

            # Upsert to review_log
            if not existing:
                log_entry = ReviewLog(
                    business_id=business.id,
                    google_review_id=review_id,
                    reviewer_name=reviewer_name,
                    star_rating=stars,
                    review_text=review_text,
                    status='pending',
                )
                db.session.add(log_entry)
                db.session.commit()

            unanswered.append({
                'review_id': review_id,
                'reviewer_name': reviewer_name,
                'star_rating': stars,
                'review_text': review_text,
            })

        logger.info(f'Found {len(unanswered)} unanswered reviews for {business.business_name}')
        return unanswered

    except Exception as e:
        logger.error(f'Error fetching reviews for business {business.id}: {e}')
        return []
