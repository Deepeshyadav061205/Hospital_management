from datetime import date, datetime, time, timedelta
from werkzeug.security import generate_password_hash
from models import (
    Appointment,
    Bill,
    BloodStock,
    City,
    Doctor,
    Hospital,
    LabTest,
    Notice,
    Payment,
    Record,
    Slot,
    User,
    db,
)
from services.hospitals import BLOOD_GROUPS

CITIES_DATA = [
    ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Delhi", "Delhi", 28.6139, 77.2090),
    ("Mumbai", "Maharashtra", 19.0760, 72.8777),
    ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Pune", "Maharashtra", 18.5204, 73.8567),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462),
]


def seed_data():
    """Populate initial demo data if the database is empty."""
    if User.query.first() is not None or City.query.first() is not None:
        return False

    # Cities, Hospitals, and Blood Stocks
    jaipur_lifeline = None
    jaipur_sanjeevani = None

    for idx, (city_name, state, lat, lng) in enumerate(CITIES_DATA):
        city = City(name=city_name, state=state, lat=lat, lng=lng)
        db.session.add(city)
        db.session.flush()

        # Offset ~2.6 km (Lifeline) and ~4.3 km (Sanjeevani) from city center
        lifeline = Hospital(
            city_id=city.id,
            name=f"{city_name} Lifeline Hospital",
            address=f"14 Station Road, {city_name}, {state}",
            phone=f"0141-240{100 + idx}",
            lat=round(lat + 0.020, 4),
            lng=round(lng + 0.015, 4),
            total_beds=120 + (idx * 5),
            available_beds=34 + (idx * 2),
            total_icu=20 + idx,
            available_icu=6 + (idx % 4),
        )
        sanjeevani = Hospital(
            city_id=city.id,
            name=f"{city_name} Sanjeevani Hospital",
            address=f"88 Civil Lines, {city_name}, {state}",
            phone=f"0141-250{200 + idx}",
            lat=round(lat - 0.032, 4),
            lng=round(lng + 0.025, 4),
            total_beds=90 + (idx * 4),
            available_beds=18 + idx,
            total_icu=15,
            available_icu=0 if city_name == "Jaipur" else 4 + (idx % 3),
        )
        db.session.add_all([lifeline, sanjeevani])
        db.session.flush()

        if city_name == "Jaipur":
            jaipur_lifeline = lifeline
            jaipur_sanjeevani = sanjeevani

        for h_offset, hosp in enumerate((lifeline, sanjeevani)):
            for b_idx, group in enumerate(BLOOD_GROUPS):
                units = 8 + ((idx + b_idx + h_offset * 3) % 12)
                if hosp is jaipur_sanjeevani and group == "O-":
                    units = 2
                db.session.add(BloodStock(hospital_id=hosp.id, blood_group=group, units=units))

    doctor_pw = generate_password_hash("Doctor@123")
    patient_pw = generate_password_hash("Patient@123")

    # Doctors
    mehta_user = User(
        name="Dr. Mehta",
        email="mehta@citycare.com",
        password_hash=doctor_pw,
        role="doctor",
        phone="9876500101",
        age=44,
    )
    rao_user = User(
        name="Dr. Rao",
        email="rao@citycare.com",
        password_hash=doctor_pw,
        role="doctor",
        phone="9876500102",
        age=39,
    )
    db.session.add_all([mehta_user, rao_user])
    db.session.flush()

    dr_mehta = Doctor(
        user_id=mehta_user.id,
        hospital_id=jaipur_lifeline.id,
        department="Cardiology",
    )
    dr_rao = Doctor(
        user_id=rao_user.id,
        hospital_id=jaipur_sanjeevani.id,
        department="General Medicine",
    )
    db.session.add_all([dr_mehta, dr_rao])
    db.session.flush()

    # Patients
    aman = User(
        name="Aman Verma",
        email="aman@example.com",
        password_hash=patient_pw,
        role="patient",
        phone="9876500001",
        age=32,
    )
    neha = User(
        name="Neha Singh",
        email="neha@example.com",
        password_hash=patient_pw,
        role="patient",
        phone="9876500002",
        age=24,
    )
    rahul = User(
        name="Rahul Sharma",
        email="rahul@example.com",
        password_hash=patient_pw,
        role="patient",
        phone="9876500003",
        age=45,
    )
    priya = User(
        name="Priya Jain",
        email="priya@example.com",
        password_hash=patient_pw,
        role="patient",
        phone="9876500004",
        age=29,
    )
    db.session.add_all([aman, neha, rahul, priya])
    db.session.flush()

    # Tomorrow's slots: 10:00 AM to 1:00 PM every 30 minutes
    tomorrow = date.today() + timedelta(days=1)
    slot_times = [
        time(10, 0),
        time(10, 30),
        time(11, 0),
        time(11, 30),
        time(12, 0),
        time(12, 30),
    ]

    mehta_slots = {}
    rao_slots = {}
    for t in slot_times:
        s_m = Slot(doctor_id=dr_mehta.id, start_time=datetime.combine(tomorrow, t), status="free")
        s_r = Slot(doctor_id=dr_rao.id, start_time=datetime.combine(tomorrow, t), status="free")
        db.session.add_all([s_m, s_r])
        mehta_slots[t] = s_m
        rao_slots[t] = s_r
    db.session.flush()

    # Mark a few slots as booked and make Dr. Rao's 11:00 AM slot full
    mehta_slots[time(10, 30)].status = "booked"
    mehta_slots[time(11, 30)].status = "booked"
    rao_slots[time(11, 0)].status = "booked"
    rao_slots[time(12, 0)].status = "booked"

    # Appointments
    now = datetime.now()
    appt_aman = Appointment(
        patient_id=aman.id,
        doctor_id=dr_mehta.id,
        slot_id=mehta_slots[time(10, 30)].id,
        reason="Routine blood pressure and cardiac follow-up",
        status="confirmed",
        created_at=now - timedelta(hours=4),
    )
    appt_priya_req = Appointment(
        patient_id=priya.id,
        doctor_id=dr_mehta.id,
        slot_id=mehta_slots[time(11, 30)].id,
        reason="Chest discomfort checkup",
        status="requested",
        created_at=now - timedelta(hours=2),
    )
    appt_rahul_rao = Appointment(
        patient_id=rahul.id,
        doctor_id=dr_rao.id,
        slot_id=rao_slots[time(11, 0)].id,
        reason="Seasonal viral fever consultation",
        status="confirmed",
        created_at=now - timedelta(hours=5),
    )
    appt_neha_wait = Appointment(
        patient_id=neha.id,
        doctor_id=dr_rao.id,
        slot_id=None,
        reason="Persistent headache and fatigue (Requested 11:00 AM slot)",
        status="waitlisted",
        created_at=now - timedelta(hours=1),
    )
    appt_past_visited = Appointment(
        patient_id=rahul.id,
        doctor_id=dr_mehta.id,
        slot_id=None,
        reason="Annual ECG screening",
        status="visited",
        created_at=now - timedelta(days=2),
    )
    appt_past_closed = Appointment(
        patient_id=priya.id,
        doctor_id=dr_rao.id,
        slot_id=None,
        reason="Throat infection follow-up",
        status="closed",
        created_at=now - timedelta(days=5),
    )
    db.session.add_all(
        [
            appt_aman,
            appt_priya_req,
            appt_rahul_rao,
            appt_neha_wait,
            appt_past_visited,
            appt_past_closed,
        ]
    )
    db.session.flush()

    # Bills and Payments
    bill_aman = Bill(
        patient_id=aman.id,
        appointment_id=appt_aman.id,
        amount=1500.0,
        paid_amount=500.0,
        due_date=date.today() + timedelta(days=7),
        status="partial",
    )
    bill_neha = Bill(
        patient_id=neha.id,
        appointment_id=None,
        amount=800.0,
        paid_amount=0.0,
        due_date=date.today() + timedelta(days=5),
        status="due",
    )
    bill_rahul = Bill(
        patient_id=rahul.id,
        appointment_id=appt_past_visited.id,
        amount=1200.0,
        paid_amount=1200.0,
        due_date=date.today() - timedelta(days=1),
        status="paid",
    )
    db.session.add_all([bill_aman, bill_neha, bill_rahul])
    db.session.flush()

    db.session.add_all(
        [
            Payment(bill_id=bill_aman.id, amount=500.0, paid_on=now - timedelta(hours=3)),
            Payment(bill_id=bill_rahul.id, amount=1200.0, paid_on=now - timedelta(days=1)),
        ]
    )

    # Medical Records & Lab Tests
    record_aman = Record(
        patient_id=aman.id,
        doctor_id=dr_mehta.id,
        diagnosis="Mild Essential Hypertension",
        prescription="Tab. Amlodipine 5mg once daily after breakfast; low-sodium diet and 30 min daily walk.",
        status="open",
        created_at=now - timedelta(days=1),
    )
    db.session.add(record_aman)
    db.session.flush()

    lab_neha = LabTest(
        patient_id=neha.id,
        record_id=None,
        test_name="Blood Sugar (Fasting & PP)",
        status="requested",
        report_text="",
    )
    db.session.add(lab_neha)

    # Notices
    db.session.add_all(
        [
            Notice(
                title="OPD timings updated",
                body="Morning OPD consultations run from 10:00 AM to 1:00 PM Monday through Saturday. Please arrive 15 minutes prior to your slot.",
                created_at=now - timedelta(days=2),
            ),
            Notice(
                title="Free health camp on Sunday",
                body="CityCare Hospital is hosting a free blood pressure, ECG, and blood sugar screening camp this Sunday from 9:00 AM to 2:00 PM.",
                created_at=now - timedelta(days=1),
            ),
        ]
    )

    db.session.commit()
    return True


if __name__ == "__main__":
    from app import create_app

    app = create_app({"AUTO_SEED": False})
    with app.app_context():
        db.create_all()
        inserted = seed_data()
        print("Seeded CityCare Hospital database." if inserted else "Database already contains data.")
