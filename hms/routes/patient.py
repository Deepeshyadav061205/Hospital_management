from datetime import date, datetime, timedelta
from io import BytesIO
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from models import Appointment, Bill, Doctor, LabTest, Notice, Record, db
from routes.auth import get_current_user, role_required
from services.appointments import (
    BookingError,
    book_appointment,
    cancel_appointment,
    get_slots_for_doctor_and_date,
)
from services.billing import BillingError, generate_receipt_pdf, record_payment
from services.records import RecordError, request_lab_test

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")


@patient_bp.route("/dashboard")
@role_required("patient")
def dashboard():
    user = get_current_user()
    appointments = (
        Appointment.query.filter_by(patient_id=user.id)
        .order_by(Appointment.created_at.desc())
        .all()
    )
    active_appointments = [
        a for a in appointments if a.status in ("requested", "under_review", "confirmed", "waitlisted")
    ]
    bills = Bill.query.filter_by(patient_id=user.id).all()
    total_due = round(sum(b.balance_due for b in bills if b.status != "paid"), 2)
    records_count = Record.query.filter_by(patient_id=user.id).count()
    pending_tests = LabTest.query.filter(
        LabTest.patient_id == user.id, LabTest.status != "completed"
    ).count()
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(3).all()

    return render_template(
        "patient/dashboard.html",
        user=user,
        active_appointments=active_appointments,
        total_due=total_due,
        records_count=records_count,
        pending_tests=pending_tests,
        notices=notices,
    )


@patient_bp.route("/book", methods=["GET", "POST"])
@role_required("patient")
def book():
    user = get_current_user()
    doctors = Doctor.query.all()
    tomorrow = date.today() + timedelta(days=1)

    if request.method == "POST":
        doctor_id_raw = request.form.get("doctor_id")
        date_raw = request.form.get("date") or tomorrow.isoformat()
        slot_id_raw = (request.form.get("slot_id") or "").strip()
        reason = request.form.get("reason") or ""
        waitlist_flag = request.form.get("waitlist") == "1"

        try:
            doctor_id = int(doctor_id_raw) if doctor_id_raw else None
            target_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
            slot_id = int(slot_id_raw) if slot_id_raw else None
        except ValueError:
            flash("Please provide valid booking details.", "error")
            return redirect(url_for("patient.book"))

        try:
            appt = book_appointment(
                patient_id=user.id,
                doctor_id=doctor_id,
                reason=reason,
                slot_id=slot_id,
                target_date=target_date,
                waitlist=waitlist_flag,
            )
            if appt.status == "waitlisted":
                flash("No free slot was chosen/available, so your request has been added to the waitlist.", "success")
            else:
                flash("Appointment requested! Waiting for doctor confirmation.", "success")
            return redirect(url_for("patient.appointments"))
        except BookingError as exc:
            flash(str(exc), "error")
            return redirect(url_for("patient.book", doctor_id=doctor_id_raw, date=date_raw))

    hospital_id = request.args.get("hospital_id", type=int)
    if hospital_id:
        hospital_doctors = [d for d in doctors if d.hospital_id == hospital_id]
        if hospital_doctors:
            doctors = hospital_doctors

    selected_doctor_id = request.args.get("doctor_id", type=int)
    if not selected_doctor_id and doctors:
        selected_doctor_id = doctors[0].id

    date_str = request.args.get("date") or tomorrow.isoformat()
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        selected_date = tomorrow
        date_str = selected_date.isoformat()

    slots = []
    if selected_doctor_id:
        slots = get_slots_for_doctor_and_date(selected_doctor_id, selected_date)

    has_free_slots = any(s.status == "free" for s in slots)

    return render_template(
        "patient/book.html",
        doctors=doctors,
        hospital_id=hospital_id,
        selected_doctor_id=selected_doctor_id,
        selected_date=date_str,
        slots=slots,
        has_free_slots=has_free_slots,
    )


@patient_bp.route("/appointments")
@role_required("patient")
def appointments():
    user = get_current_user()
    appts = (
        Appointment.query.filter_by(patient_id=user.id)
        .order_by(Appointment.created_at.desc())
        .all()
    )
    return render_template("patient/appointments.html", appointments=appts)


@patient_bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@role_required("patient")
def cancel_my_appointment(appointment_id):
    user = get_current_user()
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        abort(404)
    if appt.patient_id != user.id:
        abort(403)

    try:
        _, promoted = cancel_appointment(appointment_id, user)
        msg = "Appointment cancelled and slot released."
        if promoted:
            msg += " A waitlisted request has been moved to review."
        flash(msg, "success")
    except (BookingError, PermissionError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("patient.appointments"))


@patient_bp.route("/bills")
@role_required("patient")
def bills():
    user = get_current_user()
    patient_bills = Bill.query.filter_by(patient_id=user.id).order_by(Bill.due_date.asc()).all()
    return render_template("patient/bills.html", bills=patient_bills)


@patient_bp.route("/bills/<int:bill_id>")
@role_required("patient")
def bill_detail(bill_id):
    user = get_current_user()
    bill = db.session.get(Bill, bill_id)
    if not bill:
        abort(404)
    if bill.patient_id != user.id:
        abort(403)
    return render_template("patient/bill_detail.html", bill=bill)


@patient_bp.route("/bills/<int:bill_id>/pay", methods=["POST"])
@role_required("patient")
def pay_bill(bill_id):
    user = get_current_user()
    bill = db.session.get(Bill, bill_id)
    if not bill:
        abort(404)
    if bill.patient_id != user.id:
        abort(403)

    amount = request.form.get("amount")
    try:
        record_payment(bill_id, user.id, amount)
        flash("Payment recorded successfully.", "success")
    except (BillingError, PermissionError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("patient.bill_detail", bill_id=bill_id))


@patient_bp.route("/bills/<int:bill_id>/receipt")
@role_required("patient")
def download_receipt(bill_id):
    user = get_current_user()
    bill = db.session.get(Bill, bill_id)
    if not bill:
        abort(404)
    if bill.patient_id != user.id:
        abort(403)

    pdf_bytes = generate_receipt_pdf(bill)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"citycare_receipt_{bill.id}.pdf",
    )


@patient_bp.route("/records")
@role_required("patient")
def records():
    user = get_current_user()
    patient_records = (
        Record.query.filter_by(patient_id=user.id).order_by(Record.created_at.desc()).all()
    )
    lab_tests = LabTest.query.filter_by(patient_id=user.id).order_by(LabTest.id.desc()).all()
    return render_template("patient/records.html", records=patient_records, lab_tests=lab_tests)


@patient_bp.route("/records/<int:record_id>")
@role_required("patient")
def record_detail(record_id):
    user = get_current_user()
    record = db.session.get(Record, record_id)
    if not record:
        abort(404)
    if record.patient_id != user.id:
        abort(403)
    return render_template("patient/record_detail.html", record=record)


@patient_bp.route("/lab-tests/request", methods=["POST"])
@role_required("patient")
def create_lab_test_request():
    user = get_current_user()
    test_name = request.form.get("test_name")
    record_id_raw = (request.form.get("record_id") or "").strip()
    record_id = int(record_id_raw) if record_id_raw.isdigit() else None

    try:
        request_lab_test(user.id, test_name, record_id=record_id)
        flash("Lab test request submitted for doctor approval.", "success")
    except RecordError as exc:
        flash(str(exc), "error")
    return redirect(url_for("patient.records"))


@patient_bp.route("/notices")
@role_required("patient")
def notices():
    all_notices = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template("patient/notices.html", notices=all_notices)
