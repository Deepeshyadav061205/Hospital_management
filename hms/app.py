import hmac
import secrets
from flask import Flask, abort, render_template, request, session
from config import Config
from models import db
from routes.auth import auth_bp, get_current_user
from routes.doctor import doctor_bp
from routes.hospitals import hospitals_bp
from routes.patient import patient_bp
from seed import seed_data


def create_app(test_config=None):
    """Application factory for CityCare Hospital HMS."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(hospitals_bp)

    def get_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_hex(32)
            session["_csrf_token"] = token
        return token

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": get_csrf_token,
            "current_user": get_current_user(),
        }

    @app.before_request
    def verify_csrf():
        if request.method == "POST" and app.config.get("CSRF_ENABLED", True):
            session_token = session.get("_csrf_token", "")
            form_token = request.form.get("csrf_token", "")
            if not session_token or not form_token or not hmac.compare_digest(session_token, form_token):
                abort(403)

    @app.errorhandler(403)
    def forbidden(_err):
        return render_template("error.html", code=403, title="Access Denied", message="You do not have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(_err):
        return render_template("error.html", code=404, title="Page Not Found", message="The requested page could not be found."), 404

    with app.app_context():
        db.create_all()
        if app.config.get("AUTO_SEED", True):
            seed_data()

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
