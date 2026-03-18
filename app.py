import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

# Initialize extensions (before models import them)
db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)

    # Config
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///replyrig_dev.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Fix Railway's postgres:// -> postgresql://
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace(
            'postgres://', 'postgresql://', 1
        )

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # User loader
    from models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.google_oauth import google_oauth_bp
    from routes.stripe_webhook import stripe_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(google_oauth_bp)
    app.register_blueprint(stripe_bp)

    # Landing page
    @app.route('/')
    def landing():
        return render_template('landing.html')

    # Health check for Railway
    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    # Create tables
    with app.app_context():
        db.create_all()

    # Start background scheduler
    from scheduler.review_checker import start_scheduler
    start_scheduler(app)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
