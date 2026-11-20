from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, db

auth_bp = Blueprint("auth", __name__)


def get_current_user():
    """Return the logged-in User object, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    """Redirect anonymous visitors to the login page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(required_role):
    """Require authentication and a specific role, returning 403 for wrong roles."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            if user.role != required_role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@auth_bp.route("/")
def index():
    user = get_current_user()
    if user:
        if user.role == "doctor":
            return redirect(url_for("doctor.dashboard"))
        return redirect(url_for("patient.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html"), 400

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "error")
            return render_template("login.html"), 401

        session["user_id"] = user.id
        session["role"] = user.role
        session["user_name"] = user.name
        flash(f"Welcome back, {user.name}.", "success")
        return redirect(url_for("auth.index"))

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        phone = (request.form.get("phone") or "").strip()
        age_raw = (request.form.get("age") or "").strip()

        if not name or not email or not password or not phone or not age_raw:
            flash("All fields are required to register.", "error")
            return render_template("register.html"), 400

        try:
            age = int(age_raw)
            if age <= 0 or age > 120:
                raise ValueError
        except ValueError:
            flash("Please enter a valid age between 1 and 120.", "error")
            return render_template("register.html"), 400

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html"), 400

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html"), 400

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="patient",
            phone=phone,
            age=age,
        )
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["role"] = user.role
        session["user_name"] = user.name
        flash("Registration successful! Welcome to CityCare Hospital.", "success")
        return redirect(url_for("patient.dashboard"))

    return render_template("register.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
