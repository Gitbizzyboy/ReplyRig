from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import db
from models.waitlist import WaitlistEntry

waitlist_bp = Blueprint('waitlist', __name__)


@waitlist_bp.route('/waitlist', methods=['GET', 'POST'])
def waitlist():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()

        if not email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('waitlist.waitlist'))

        existing = WaitlistEntry.query.filter_by(email=email).first()
        if existing:
            flash("You're already on the list! We'll be in touch soon.", 'info')
            return redirect(url_for('waitlist.waitlist'))

        entry = WaitlistEntry(email=email, name=name or None, source='website')
        db.session.add(entry)
        db.session.commit()

        return render_template('waitlist_success.html')

    return render_template('waitlist.html')
