from flask import Blueprint, abort, render_template
from sqlalchemy import func
from models import City, Hospital, db
from services.hospitals import low_stock, nearest_hospitals, serialize_hospitals

hospitals_bp = Blueprint("hospitals", __name__, url_prefix="/hospitals")


@hospitals_bp.route("")
def index():
    cities = City.query.order_by(City.name.asc()).all()
    all_hospitals = Hospital.query.order_by(Hospital.name.asc()).all()
    return render_template(
        "hospitals/index.html",
        cities=cities,
        hospitals_json=serialize_hospitals(all_hospitals),
    )


@hospitals_bp.route("/city/<city_name>")
def by_city(city_name):
    city = City.query.filter(func.lower(City.name) == city_name.strip().lower()).first()
    if not city:
        abort(404)

    hospitals = nearest_hospitals(city)
    alerts = {h.id: low_stock(h) for h in hospitals}
    return render_template(
        "hospitals/city.html",
        city=city,
        hospitals=hospitals,
        alerts=alerts,
        hospitals_json=serialize_hospitals(hospitals),
    )


@hospitals_bp.route("/<int:hospital_id>")
def detail(hospital_id):
    hospital = db.session.get(Hospital, hospital_id)
    if not hospital:
        abort(404)

    alerts = low_stock(hospital)
    return render_template(
        "hospitals/detail.html",
        hospital=hospital,
        alerts=alerts,
        hospitals_json=serialize_hospitals([hospital]),
    )
