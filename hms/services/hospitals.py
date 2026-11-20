import math
from sqlalchemy import func
from models import BloodStock, City, Hospital, db

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class HospitalValidationError(ValueError):
    """Raised when hospital bed, ICU, or blood unit values fail validation."""


def haversine_km(lat1, lng1, lat2, lng2):
    """Calculate straight-line great-circle distance in kilometers using pure Python."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_hospitals(city):
    """Return hospitals in a city (City model or name) sorted by ascending distance from city center."""
    if isinstance(city, str):
        city_obj = City.query.filter(func.lower(City.name) == city.strip().lower()).first()
    else:
        city_obj = city

    if not city_obj:
        return []

    hospitals = Hospital.query.filter_by(city_id=city_obj.id).all()
    ranked = []
    for hosp in hospitals:
        dist = haversine_km(city_obj.lat, city_obj.lng, hosp.lat, hosp.lng)
        hosp.distance_km = round(dist, 1)
        ranked.append((dist, hosp))

    ranked.sort(key=lambda item: item[0])
    return [item[1] for item in ranked]


def low_stock(hospital):
    """
    Flag low hospital resources:
    - beds or ICU at 10% or less of total
    - blood units under 5
    """
    low_beds = hospital.total_beds == 0 or hospital.available_beds * 10 <= hospital.total_beds
    low_icu = hospital.total_icu == 0 or hospital.available_icu * 10 <= hospital.total_icu
    low_blood = [stock.blood_group for stock in hospital.blood_stocks if stock.units < 5]
    return {
        "beds": low_beds,
        "icu": low_icu,
        "blood": low_blood,
    }


def serialize_hospitals(hospitals):
    """Serialize hospitals into JSON-safe dictionaries for Leaflet map markers."""
    return [
        {
            "id": h.id,
            "name": h.name,
            "lat": h.lat,
            "lng": h.lng,
            "available_beds": h.available_beds,
            "total_beds": h.total_beds,
            "available_icu": h.available_icu,
            "total_icu": h.total_icu,
            "url": f"/hospitals/{h.id}",
        }
        for h in hospitals
    ]


def update_hospital_availability(hospital, total_beds, available_beds, total_icu, available_icu, blood_units):
    """Validate and update a hospital's beds, ICU counts, and blood stock units."""
    try:
        t_beds = int(total_beds)
        a_beds = int(available_beds)
        t_icu = int(total_icu)
        a_icu = int(available_icu)
    except (TypeError, ValueError):
        raise HospitalValidationError("Beds and ICU counts must be whole numbers.")

    if t_beds < 0 or a_beds < 0 or a_beds > t_beds:
        raise HospitalValidationError("Beds must satisfy 0 <= available beds <= total beds.")
    if t_icu < 0 or a_icu < 0 or a_icu > t_icu:
        raise HospitalValidationError("ICU beds must satisfy 0 <= available ICU <= total ICU.")

    parsed_blood = {}
    for group in BLOOD_GROUPS:
        try:
            units = int(blood_units.get(group, 0))
        except (TypeError, ValueError):
            raise HospitalValidationError(f"Blood units for {group} must be a whole number.")
        if units < 0:
            raise HospitalValidationError(f"Blood units for {group} cannot be negative.")
        parsed_blood[group] = units

    hospital.total_beds = t_beds
    hospital.available_beds = a_beds
    hospital.total_icu = t_icu
    hospital.available_icu = a_icu

    existing_stocks = {s.blood_group: s for s in hospital.blood_stocks}
    for group, units in parsed_blood.items():
        if group in existing_stocks:
            existing_stocks[group].units = units
        else:
            db.session.add(BloodStock(hospital_id=hospital.id, blood_group=group, units=units))

    db.session.commit()
    return hospital
