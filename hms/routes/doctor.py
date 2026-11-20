from datetime import date, datetime, time, timedelta
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from models import Appointment, Bill, LabTest, Record, Slot, User, db
from routes.auth import get_current_user, role_required
from services.appointments import (
    BookingError,
    cancel_appointment,
    check_in_appointment,
    close_appointment,
    confirm_appointment,
    review_appointment,
)
from services.billing import BillingError, create_bill
from services.hospitals import BLOOD_GROUPS, HospitalValidationError, low_stock, update_hospital_availability
from services.records import RecordError, approve_lab_test, close_record, complete_lab_test, create_record

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")


@doctor_bp.route("/dashboard")
@role_required("doctor")
def dashboard():
    user = get_current_user()
    today_start = datetime.combine(date.today(), time.min)
    today_end = today_start + timedelta(days=1)

    todays_appointments = (
        Appointment.query.join(Slot, Appointment.slot_id == Slot.id)
        .filter(
            Slot.start_time >= today_start,
            Slot.start_time < today_end,
            Appointment.status.in_(["confirmed", "visited"]),
        )
        .order_by(Slot.start_time.asc())
        .all()
    )
    upcoming_appointments = (
        Appointment.query.join(Slot, Appointment.slot_id == Slot.id)
        .filter(
            Slot.start_time >= today_start,
            Appointment.status.in_(["confirmed", "visited"]),
        )
        .order_by(Slot.start_time.asc())
        .all()
    )
    pending_bills_count = Bill.query.filter(Bill.status.in_(["due", "partial"])).count()
    open_requests_count = Appointment.query.filter(
        Appointment.status.in_(["requested", "under_review", "waitlisted"])
    ).count()
    pending_labs_count = LabTest.query.filter(LabTest.status != "completed").count()

    return render_template(
        "doctor/dashboard.html",
        user=user,
        todays_appointments=todays_appointments,
        upcoming_appointments=upcoming_appointments,
        pending_bills_count=pending_bills_count,
        open_requests_count=open_requests_count,
        pending_labs_count=pending_labs_count,
    )


@doctor_bp.route("/requests")
@role_required("doctor")
def requests_list():
    appointments = Appointment.query.order_by(Appointment.created_at.desc()).all()
    return render_template("doctor/requests.html", appointments=appointments)


@doctor_bp.route("/appointments/<int:appointment_id>/action", methods=["POST"])
@role_required("doctor")
def appointment_action(appointment_id):
    user = get_current_user()
    action = request.form.get("action")

    try:
        if action == "review":
            review_appointment(appointment_id)
            flash("Appointment moved to under review.", "success")
        elif action == "confirm":
            confirm_appointment(appointment_id)
            flash("Appointment confirmed.", "success")
        elif action == "checkin":
            check_in_appointment(appointment_id)
            flash("Patient checked in (visited).", "success")
        elif action == "close":
            close_appointment(appointment_id)
            flash("Visit closed.", "success")
        elif action == "reject":
            _, promoted = cancel_appointment(appointment_id, user)
            msg = "Appointment rejected/cancelled."
            if promoted:
                msg += " Oldest waitlisted request moved to under review."
            flash(msg, "success")
        else:
            flash("Unknown action.", "error")
    except (BookingError, PermissionError) as exc:
        flash(str(exc), "error")

    return redirect(url_for("doctor.requests_list"))


@doctor_bp.route("/patients")
@role_required("doctor")
def patients():
    query = (request.args.get("q") or "").strip().lower()
    all_patients = User.query.filter_by(role="patient").order_by(User.name.asc()).all()
    if query:
        all_patients = [
            p for p in all_patients if query in p.name.lower() or query in p.email.lower() or query in p.phone
        ]
    return render_template("doctor/patients.html", patients=all_patients, search_query=query)


@doctor_bp.route("/patients/<int:patient_id>")
@role_required("doctor")
def patient_detail(patient_id):
    patient = db.session.get(User, patient_id)
    if not patient or patient.role != "patient":
        abort(404)

    records = Record.query.filter_by(patient_id=patient.id).order_by(Record.created_at.desc()).all()
    lab_tests = LabTest.query.filter_by(patient_id=patient.id).order_by(LabTest.id.desc()).all()
    bills = Bill.query.filter_by(patient_id=patient.id).order_by(Bill.due_date.desc()).all()
    appointments = (
        Appointment.query.filter_by(patient_id=patient.id)
        .order_by(Appointment.created_at.desc())
        .all()
    )
    default_due = (date.today() + timedelta(days=7)).isoformat()

    return render_template(
        "doctor/patient_detail.html",
        patient=patient,
        records=records,
        lab_tests=lab_tests,
        bills=bills,
        appointments=appointments,
        default_due=default_due,
    )


@doctor_bp.route("/patients/<int:patient_id>/records", methods=["POST"])
@role_required("doctor")
def add_record(patient_id):
    user = get_current_user()
    patient = db.session.get(User, patient_id)
    if not patient or patient.role != "patient":
        abort(404)
    if not user.doctor_profile:
        abort(403)

    diagnosis = request.form.get("diagnosis")
    prescription = request.form.get("prescription")
    try:
        create_record(patient.id, user.doctor_profile.id, diagnosis, prescription)
        flash("Medical record and prescription saved.", "success")
    except RecordError as exc:
        flash(str(exc), "error")
    return redirect(url_for("doctor.patient_detail", patient_id=patient.id))


@doctor_bp.route("/records/<int:record_id>/close", methods=["POST"])
@role_required("doctor")
def close_patient_record(record_id):
    record = db.session.get(Record, record_id)
    if not record:
        abort(404)
    try:
        close_record(record_id)
        flash("Record marked as closed.", "success")
    except RecordError as exc:
        flash(str(exc), "error")
    return redirect(url_for("doctor.patient_detail", patient_id=record.patient_id))


@doctor_bp.route("/patients/<int:patient_id>/bills", methods=["POST"])
@role_required("doctor")
def add_bill(patient_id):
    patient = db.session.get(User, patient_id)
    if not patient or patient.role != "patient":
        abort(404)

    amount = request.form.get("amount")
    due_date_raw = request.form.get("due_date") or (date.today() + timedelta(days=7)).isoformat()
    try:
        due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
        create_bill(patient.id, amount, due_date)
        flash("Bill created for patient.", "success")
    except (ValueError, BillingError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("doctor.patient_detail", patient_id=patient.id))


@doctor_bp.route("/lab-tests/<int:test_id>/approve", methods=["POST"])
@role_required("doctor")
def approve_test(test_id):
    test = db.session.get(LabTest, test_id)
    if not test:
        abort(404)
    try:
        approve_lab_test(test_id)
        flash(f"Lab test '{test.test_name}' approved.", "success")
    except RecordError as exc:
        flash(str(exc), "error")
    next_url = request.form.get("next") or url_for("doctor.patient_detail", patient_id=test.patient_id)
    return redirect(next_url)


@doctor_bp.route("/lab-tests/<int:test_id>/complete", methods=["POST"])
@role_required("doctor")
def complete_test(test_id):
    test = db.session.get(LabTest, test_id)
    if not test:
        abort(404)
    report_text = request.form.get("report_text")
    try:
        complete_lab_test(test_id, report_text)
        flash(f"Lab report saved for '{test.test_name}'.", "success")
    except RecordError as exc:
        flash(str(exc), "error")
    next_url = request.form.get("next") or url_for("doctor.patient_detail", patient_id=test.patient_id)
    return redirect(next_url)


@doctor_bp.route("/reports")
@role_required("doctor")
def reports():
    lab_tests = LabTest.query.order_by(LabTest.id.desc()).all()
    records = Record.query.order_by(Record.created_at.desc()).all()
    return render_template("doctor/reports.html", lab_tests=lab_tests, records=records)


@doctor_bp.route("/hospital", methods=["GET", "POST"])
@role_required("doctor")
def hospital():
    user = get_current_user()
    doctor = user.doctor_profile
    hosp = doctor.hospital if doctor else None
    if not hosp:
        flash("No hospital is assigned to your doctor profile yet.", "error")
        return redirect(url_for("doctor.dashboard"))

    if request.method == "POST":
        blood_units = {group: request.form.get(f"blood_{group}") for group in BLOOD_GROUPS}
        try:
            update_hospital_availability(
                hosp,
                total_beds=request.form.get("total_beds"),
                available_beds=request.form.get("available_beds"),
                total_icu=request.form.get("total_icu"),
                available_icu=request.form.get("available_icu"),
                blood_units=blood_units,
            )
            flash(f"Updated availability for {hosp.name}.", "success")
            return redirect(url_for("doctor.hospital"))
        except HospitalValidationError as exc:
            flash(str(exc), "error")
            return render_template(
                "doctor/hospital.html",
                hospital=hosp,
                blood_groups=BLOOD_GROUPS,
                alerts=low_stock(hosp),
            ), 400

    return render_template(
        "doctor/hospital.html",
        hospital=hosp,
        blood_groups=BLOOD_GROUPS,
        alerts=low_stock(hosp),
    )
