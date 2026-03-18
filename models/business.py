from datetime import datetime, timezone
from app import db


class Business(db.Model):
    __tablename__ = 'businesses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    google_location_id = db.Column(db.String(255), nullable=False)
    business_name = db.Column(db.String(255))
    google_access_token = db.Column(db.Text)
    google_refresh_token = db.Column(db.Text)
    token_expiry = db.Column(db.DateTime(timezone=True))
    auto_reply_enabled = db.Column(db.Boolean, default=True)
    reply_tone = db.Column(db.String(20), default='professional')  # professional, friendly, formal
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    review_logs = db.relationship('ReviewLog', backref='business', lazy=True, cascade='all, delete-orphan')

    @property
    def total_reviews(self):
        return ReviewLog.query.filter_by(business_id=self.id).count()

    @property
    def replied_reviews(self):
        return ReviewLog.query.filter_by(business_id=self.id, status='replied').count()

    @property
    def pending_reviews(self):
        return ReviewLog.query.filter_by(business_id=self.id, status='pending').count()

    def __repr__(self):
        return f'<Business {self.business_name}>'


class ReviewLog(db.Model):
    __tablename__ = 'review_log'

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False)
    google_review_id = db.Column(db.String(255), unique=True, nullable=False)
    reviewer_name = db.Column(db.String(255))
    star_rating = db.Column(db.Integer)
    review_text = db.Column(db.Text)
    reply_text = db.Column(db.Text)
    replied_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(20), default='pending')  # pending, replied, skipped, failed

    def __repr__(self):
        return f'<ReviewLog {self.google_review_id} - {self.status}>'
