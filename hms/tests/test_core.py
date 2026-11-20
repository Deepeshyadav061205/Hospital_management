import os
import re
import sys
from datetime import date, datetime, time, timedelta
import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import Appointment, Bill, City, Doctor, Hospital, Record, Slot, User, db
from seed import seed_data
from services.appointments import (
    BookingError,
    book_appointment,
    cancel_appointment,
    check_in_appointment,
    close_appointment,
    confirm_appointment,
    review_appointment,
)
from services.billing import generate_receipt_pdf, record_payment
from services.hospitals import BLOOD_GROUPS, haversine_km, low_stock, nearest_hospitals


@pytest.fixture
def app(tmp_path):
    db_file = tmp_path / "test_hms.db"
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
            "AUTO_SEED": False,
            "SECRET_KEY": "test-secret",
        }
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(name, email, role="patient", password="Password@123"):
    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        phone="9876543210",
        age=30,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _login(client, email, password="Password@123"):
    resp = client.get("/login")
    match = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
    token = match.group(1)
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
        follow_redirects=False,
    )


def test_two_patients_cannot_book_same_slot(app):
    with app.app_context():
        doc_user = _create_user("Dr. Test", "doc@citycare.com", role="doctor")
        doctor = Doctor(user_id=doc_user.id, department="Cardiology")
        db.session.add(doctor)
        p1 = _create_user("Patient One", "p1@example.com")
        p2 = _create_user("Patient Two", "p2@example.com")
        db.session.flush()

        slot = Slot(
            doctor_id=doctor.id,
            start_time=datetime.combine(date.today() + timedelta(days=1), time(10, 0)),
            status="free",
        )
        db.session.add(slot)
        db.session.commit()

        appt1 = book_appointment(p1.id, doctor.id, "Checkup", slot_id=slot.id)
        assert appt1.status == "requested"
        assert db.session.get(Slot, slot.id).status == "booked"

        with pytest.raises(BookingError):
            book_appointment(p2.id, doctor.id, "Checkup 2", slot_id=slot.id)


def test_full_slot_creates_waitlisted_request(app):
    with app.app_context():
        doc_user = _create_user("Dr. Test", "doc2@citycare.com", role="doctor")
        doctor = Doctor(user_id=doc_user.id, department="General")
        db.session.add(doctor)
        p1 = _create_user("Patient One", "p1b@example.com")
        p2 = _create_user("Patient Two", "p2b@example.com")
        db.session.flush()

        tomorrow = date.today() + timedelta(days=1)
        slot = Slot(doctor_id=doctor.id, start_time=datetime.combine(tomorrow, time(11, 0)), status="free")
        db.session.add(slot)
        db.session.commit()

        book_appointment(p1.id, doctor.id, "Fever", slot_id=slot.id)
        waitlisted = book_appointment(p2.id, doctor.id, "Headache", slot_id=None, target_date=tomorrow)
        assert waitlisted.status == "waitlisted"
        assert waitlisted.slot_id is None


def test_cancel_booking_promotes_oldest_waitlisted_request(app):
    with app.app_context():
        doc_user = _create_user("Dr. Rao", "rao@citycare.com", role="doctor")
        doctor = Doctor(user_id=doc_user.id, department="General")
        db.session.add(doctor)
        p1 = _create_user("First", "first@example.com")
        p2 = _create_user("Second", "second@example.com")
        p3 = _create_user("Third", "third@example.com")
        db.session.flush()

        tomorrow = date.today() + timedelta(days=1)
        slot = Slot(doctor_id=doctor.id, start_time=datetime.combine(tomorrow, time(11, 0)), status="free")
        db.session.add(slot)
        db.session.commit()

        booked = book_appointment(p1.id, doctor.id, "Consultation", slot_id=slot.id)
        review_appointment(booked.id)
        confirm_appointment(booked.id)

        older_wait = Appointment(
            patient_id=p2.id,
            doctor_id=doctor.id,
            slot_id=None,
            reason="Older wait",
            status="waitlisted",
            created_at=datetime(2026, 1, 1, 9, 0),
        )
        newer_wait = Appointment(
            patient_id=p3.id,
            doctor_id=doctor.id,
            slot_id=None,
            reason="Newer wait",
            status="waitlisted",
            created_at=datetime(2026, 1, 1, 10, 0),
        )
        db.session.add_all([older_wait, newer_wait])
        db.session.commit()

        cancelled, promoted = cancel_appointment(booked.id, p1)
        assert cancelled.status == "cancelled"
        assert db.session.get(Slot, slot.id).status == "free"
        assert promoted.id == older_wait.id
        assert db.session.get(Appointment, older_wait.id).status == "under_review"
        assert db.session.get(Appointment, newer_wait.id).status == "waitlisted"

        # Confirming promoted request assigns the freed slot and allows check-in -> close
        confirm_appointment(older_wait.id)
        assert db.session.get(Appointment, older_wait.id).status == "confirmed"
        check_in_appointment(older_wait.id)
        assert db.session.get(Appointment, older_wait.id).status == "visited"
        close_appointment(older_wait.id)
        assert db.session.get(Appointment, older_wait.id).status == "closed"


def test_patient_gets_403_on_doctor_route(app, client):
    with app.app_context():
        _create_user("Patient User", "pat@example.com", role="patient")
        db.session.commit()

    login_resp = _login(client, "pat@example.com")
    assert login_resp.status_code == 302

    for path in ["/doctor/dashboard", "/doctor/requests", "/doctor/patients", "/doctor/reports"]:
        resp = client.get(path)
        assert resp.status_code == 403


def test_patient_cannot_open_another_patients_bill_or_record(app, client):
    with app.app_context():
        doc_user = _create_user("Dr. Mehta", "mehta@citycare.com", role="doctor")
        doctor = Doctor(user_id=doc_user.id, department="Cardiology")
        db.session.add(doctor)
        p1 = _create_user("Aman", "aman@example.com")
        p2 = _create_user("Neha", "neha@example.com")
        db.session.flush()

        bill_p2 = Bill(
            patient_id=p2.id,
            amount=800.0,
            paid_amount=0.0,
            due_date=date.today() + timedelta(days=5),
            status="due",
        )
        rec_p2 = Record(
            patient_id=p2.id,
            doctor_id=doctor.id,
            diagnosis="Migraine",
            prescription="Rest and hydration",
            status="open",
        )
        db.session.add_all([bill_p2, rec_p2])
        db.session.commit()
        bill_id = bill_p2.id
        rec_id = rec_p2.id

    _login(client, "aman@example.com")
    assert client.get(f"/patient/bills/{bill_id}").status_code == 403
    assert client.get(f"/patient/bills/{bill_id}/receipt").status_code == 403
    assert client.get(f"/patient/records/{rec_id}").status_code == 403


def test_payment_updates_bill_status(app):
    with app.app_context():
        patient = _create_user("Aman", "aman2@example.com")
        bill = Bill(
            patient_id=patient.id,
            amount=1500.0,
            paid_amount=0.0,
            due_date=date.today() + timedelta(days=7),
            status="due",
        )
        db.session.add(bill)
        db.session.commit()

        assert bill.status == "due"
        record_payment(bill.id, patient.id, 500.0)
        assert bill.status == "partial"
        assert bill.paid_amount == 500.0

        record_payment(bill.id, patient.id, 1000.0)
        assert bill.status == "paid"
        assert bill.paid_amount == 1500.0
        assert bill.balance_due == 0.0


def test_pdf_receipt_generated_and_non_zero(app, client):
    with app.app_context():
        patient = _create_user("Rahul", "rahul@example.com")
        bill = Bill(
            patient_id=patient.id,
            amount=1200.0,
            paid_amount=0.0,
            due_date=date.today(),
            status="due",
        )
        db.session.add(bill)
        db.session.commit()
        record_payment(bill.id, patient.id, 1200.0)
        bill_id = bill.id

        pdf_bytes = generate_receipt_pdf(bill)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    _login(client, "rahul@example.com")
    resp = client.get(f"/patient/bills/{bill_id}/receipt")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert len(resp.data) > 0


def test_nearest_hospitals_jaipur_sorted(app):
    with app.app_context():
        seed_data()
        hospitals = nearest_hospitals("Jaipur")
        assert len(hospitals) == 2
        distances = [h.distance_km for h in hospitals]
        assert distances == sorted(distances)
        assert all(2.0 <= d <= 6.0 for d in distances)


def test_jaipur_to_delhi_distance(app):
    with app.app_context():
        seed_data()
        jaipur = City.query.filter_by(name="Jaipur").first()
        delhi = City.query.filter_by(name="Delhi").first()
        dist = haversine_km(jaipur.lat, jaipur.lng, delhi.lat, delhi.lng)
        assert 220 <= dist <= 250


def test_public_hospital_pages_without_login(app, client):
    with app.app_context():
        seed_data()

    res_index = client.get("/hospitals")
    assert res_index.status_code == 200
    assert b"Jaipur" in res_index.data

    res_city = client.get("/hospitals/city/Jaipur")
    assert res_city.status_code == 200
    html = res_city.get_data(as_text=True)
    assert "Jaipur Lifeline Hospital" in html
    assert "Jaipur Sanjeevani Hospital" in html


def test_doctor_can_update_hospital_and_patient_gets_403(app, client):
    with app.app_context():
        seed_data()
        mehta = User.query.filter_by(email="mehta@citycare.com").first()
        hosp_id = mehta.doctor_profile.hospital_id

    # Patient gets 403 on /doctor/hospital
    _login(client, "aman@example.com", "Patient@123")
    assert client.get("/doctor/hospital").status_code == 403
    client.post("/logout", data={"csrf_token": re.search(
        r'name="csrf_token" value="([^"]+)"', client.get("/patient/dashboard").get_data(as_text=True)
    ).group(1)})

    # Doctor updates their own hospital availability
    _login(client, "mehta@citycare.com", "Doctor@123")
    page = client.get("/doctor/hospital")
    assert page.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    form_data = {
        "csrf_token": token,
        "total_beds": "150",
        "available_beds": "45",
        "total_icu": "25",
        "available_icu": "8",
    }
    for group in BLOOD_GROUPS:
        form_data[f"blood_{group}"] = "12"

    update_resp = client.post("/doctor/hospital", data=form_data, follow_redirects=True)
    assert update_resp.status_code == 200

    with app.app_context():
        hosp = db.session.get(Hospital, hosp_id)
        assert hosp.total_beds == 150
        assert hosp.available_beds == 45
        assert hosp.available_icu == 8

    # Changes appear on public hospital pages right away
    public_detail = client.get(f"/hospitals/{hosp_id}")
    assert public_detail.status_code == 200
    detail_html = public_detail.get_data(as_text=True)
    assert "45 / 150" in detail_html
    assert "8 / 25" in detail_html


def test_available_beds_greater_than_total_rejected(app, client):
    with app.app_context():
        seed_data()
        mehta = User.query.filter_by(email="mehta@citycare.com").first()
        hosp_id = mehta.doctor_profile.hospital_id
        orig_beds = db.session.get(Hospital, hosp_id).available_beds

    _login(client, "mehta@citycare.com", "Doctor@123")
    page = client.get("/doctor/hospital")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    form_data = {
        "csrf_token": token,
        "total_beds": "50",
        "available_beds": "80",
        "total_icu": "10",
        "available_icu": "4",
    }
    for group in BLOOD_GROUPS:
        form_data[f"blood_{group}"] = "10"

    resp = client.post("/doctor/hospital", data=form_data)
    assert resp.status_code == 400
    assert "0 &lt;= available beds &lt;= total beds" in resp.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(Hospital, hosp_id).available_beds == orig_beds


def test_jaipur_sanjeevani_low_icu_and_o_minus(app):
    with app.app_context():
        seed_data()
        hosp = Hospital.query.filter_by(name="Jaipur Sanjeevani Hospital").first()
        assert hosp is not None
        flags = low_stock(hosp)
        assert flags["icu"] is True
        assert "O-" in flags["blood"]
