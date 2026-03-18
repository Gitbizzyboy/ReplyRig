import logging
from googleapiclient.discovery import build
from models.business import Business, ReviewLog
from services.google_reviews import get_credentials
from app import db
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def post_reply(business: Business, review_log: ReviewLog, reply_text: str) -> bool:
    """
    Post a reply to a Google review.

    Returns True on success, False on failure.
    """
    try:
        creds = get_credentials(business)
        service = build('mybusinessreviews', 'v1', credentials=creds)

        # Google My Business API: PUT locations/{locationId}/reviews/{reviewId}/reply
        review_name = review_log.google_review_id  # "locations/.../reviews/..."

        service.locations().reviews().updateReply(
            name=review_name,
            body={'comment': reply_text},
        ).execute()

        # Update our DB record
        review_log.reply_text = reply_text
        review_log.replied_at = datetime.now(timezone.utc)
        review_log.status = 'replied'
        db.session.commit()

        logger.info(
            f'Successfully posted reply to review {review_log.id} '
            f'for {business.business_name}'
        )
        return True

    except Exception as e:
        logger.error(
            f'Failed to post reply for review {review_log.id} '
            f'(business {business.id}): {e}'
        )
        review_log.status = 'failed'
        db.session.commit()
        return False
