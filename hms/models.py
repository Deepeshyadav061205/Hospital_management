from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    """Return current UTC time as a naive datetime for consistent SQLite/MySQL storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class City(db.Model):
    __tablename__ = "cities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    state = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    hospitals = db.relationship("Hospital", back_populates="city", order_by="Hospital.name.asc()")


class Hospital(db.Model):
    __tablename__ = "hospitals"

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    total_beds = db.Column(db.Integer, nullable=False, default=0)
    available_beds = db.Column(db.Integer, nullable=False, default=0)
    total_icu = db.Column(db.Integer, nullable=False, default=0)
    available_icu = db.Column(db.Integer, nullable=False, default=0)

    city = db.relationship("City", back_populates="hospitals")
    blood_stocks = db.relationship("BloodStock", back_populates="hospital", order_by="BloodStock.id.asc()")
    doctors = db.relationship("Doctor", back_populates="hospital")


class BloodStock(db.Model):
    __tablename__ = "blood_stocks"
    __table_args__ = (db.UniqueConstraint("hospital_id", "blood_group", name="uq_hospital_blood_group"),)

    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    units = db.Column(db.Integer, nullable=False, default=0)

    hospital = db.relationship("Hospital", back_populates="blood_stocks")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # patient | doctor
    phone = db.Column(db.String(20), nullable=False, default="")
    age = db.Column(db.Integer, nullable=True)

    doctor_profile = db.relationship("Doctor", back_populates="user", uselist=False)


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospitals.id"), nullable=True)
    department = db.Column(db.String(100), nullable=False)

    user = db.relationship("User", back_populates="doctor_profile")
    hospital = db.relationship("Hospital", back_populates="doctors")
    slots = db.relationship("Slot", back_populates="doctor", lazy="dynamic")


class Slot(db.Model):
    __tablename__ = "slots"
    __table_args__ = (db.UniqueConstraint("doctor_id", "start_time", name="uq_doctor_slot_time"),)

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="free")  # free | booked

    doctor = db.relationship("Doctor", back_populates="slots")


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("slots.id"), nullable=True)
    reason = db.Column(db.String(300), nullable=False)
    # requested | under_review | confirmed | waitlisted | visited | closed | cancelled
    status = db.Column(db.String(20), nullable=False, default="requested")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    patient = db.relationship("User", foreign_keys=[patient_id])
    doctor = db.relationship("Doctor", foreign_keys=[doctor_id])
    slot = db.relationship("Slot", foreign_keys=[slot_id])


class Bill(db.Model):
    __tablename__ = "bills"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, nullable=False, default=0.0)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="due")  # due | partial | paid

    patient = db.relationship("User", foreign_keys=[patient_id])
    appointment = db.relationship("Appointment", foreign_keys=[appointment_id])
    payments = db.relationship("Payment", back_populates="bill", order_by="Payment.paid_on.asc()")

    @property
    def balance_due(self):
        return max(0.0, round(self.amount - self.paid_amount, 2))


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_on = db.Column(db.DateTime, nullable=False, default=utcnow)

    bill = db.relationship("Bill", back_populates="payments")


class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    diagnosis = db.Column(db.String(300), nullable=False)
    prescription = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")  # open | closed
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    patient = db.relationship("User", foreign_keys=[patient_id])
    doctor = db.relationship("Doctor", foreign_keys=[doctor_id])
    lab_tests = db.relationship("LabTest", back_populates="record")


class LabTest(db.Model):
    __tablename__ = "lab_tests"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    record_id = db.Column(db.Integer, db.ForeignKey("records.id"), nullable=True)
    test_name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="requested")  # requested | approved | completed
    report_text = db.Column(db.Text, nullable=False, default="")

    patient = db.relationship("User", foreign_keys=[patient_id])
    record = db.relationship("Record", back_populates="lab_tests")


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
