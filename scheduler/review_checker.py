import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = None


def process_all_businesses(app):
    """
    Main scheduled job: runs hourly to find unanswered reviews and auto-reply.
    Only processes businesses whose owner is on the 'pro' plan.
    """
    from models.business import Business, ReviewLog
    from models.user import User
    from services.google_reviews import fetch_unanswered_reviews
    from services.ai_responder import generate_response
    from services.review_poster import post_reply

    with app.app_context():
        # Only pro users get auto-replies
        pro_user_ids = [u.id for u in User.query.filter_by(plan='pro').all()]
        if not pro_user_ids:
            logger.info('No pro users found — skipping review check')
            return

        businesses = (
            Business.query
            .filter(Business.user_id.in_(pro_user_ids))
            .filter_by(auto_reply_enabled=True)
            .all()
        )

        logger.info(f'Checking {len(businesses)} businesses for unanswered reviews...')

        for biz in businesses:
            if not biz.google_refresh_token:
                logger.warning(f'Business {biz.id} has no refresh token — skipping')
                continue

            try:
                unanswered = fetch_unanswered_reviews(biz)
            except Exception as e:
                logger.error(f'Failed to fetch reviews for business {biz.id}: {e}')
                continue

            for review_data in unanswered:
                review_id = review_data['review_id']
                review_log = ReviewLog.query.filter_by(google_review_id=review_id).first()

                if not review_log or review_log.status != 'pending':
                    continue

                try:
                    reply_text = generate_response(
                        business_name=biz.business_name or 'Our Business',
                        business_type=_infer_business_type(biz.business_name),
                        reviewer_name=review_data['reviewer_name'],
                        star_rating=review_data['star_rating'],
                        review_text=review_data['review_text'],
                        tone=biz.reply_tone,
                    )
                except Exception as e:
                    logger.error(f'AI generation failed for review {review_log.id}: {e}')
                    review_log.status = 'failed'
                    from app import db
                    db.session.commit()
                    continue

                success = post_reply(biz, review_log, reply_text)
                if success:
                    logger.info(
                        f'Auto-replied to {review_data["reviewer_name"]} '
                        f'({review_data["star_rating"]}★) for {biz.business_name}'
                    )


def _infer_business_type(business_name: str) -> str:
    """
    Try to infer business type from name keywords.
    Falls back to a generic trades description.
    """
    if not business_name:
        return 'home services'

    name_lower = business_name.lower()
    if any(k in name_lower for k in ['hvac', 'heating', 'cooling', 'air', 'ac ']):
        return 'HVAC and heating/cooling'
    if any(k in name_lower for k in ['plumb', 'drain', 'pipe']):
        return 'plumbing'
    if any(k in name_lower for k in ['electric', 'wiring', 'panel']):
        return 'electrical'
    if any(k in name_lower for k in ['roof', 'gutters']):
        return 'roofing'
    if any(k in name_lower for k in ['paint']):
        return 'painting'
    if any(k in name_lower for k in ['landscape', 'lawn']):
        return 'landscaping'
    return 'home services and trades'


def start_scheduler(app):
    """Start the APScheduler background job."""
    global _scheduler

    # Don't start in debug reloader subprocess
    import os
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            func=lambda: process_all_businesses(app),
            trigger=IntervalTrigger(hours=1),
            id='review_checker',
            name='Check and respond to Google reviews',
            replace_existing=True,
            misfire_grace_time=300,
        )
        _scheduler.start()
        logger.info('Review checker scheduler started (runs every hour)')

    return _scheduler
