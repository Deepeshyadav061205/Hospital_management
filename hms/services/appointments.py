from datetime import datetime, time, timedelta
from models import Appointment, Doctor, Slot, db


class BookingError(ValueError):
    """Raised when an appointment booking or status transition violates rules."""


def get_slots_for_doctor_and_date(doctor_id, target_date):
    """Return all slots for a doctor on a given date, ordered by start_time."""
    start_dt = datetime.combine(target_date, time.min)
    end_dt = start_dt + timedelta(days=1)
    return (
        Slot.query.filter(
            Slot.doctor_id == doctor_id,
            Slot.start_time >= start_dt,
            Slot.start_time < end_dt,
        )
        .order_by(Slot.start_time.asc())
        .all()
    )


def book_appointment(patient_id, doctor_id, reason, slot_id=None, target_date=None, waitlist=False):
    """
    Book a free slot inside a transaction, or create a waitlisted request when no slot is free.
    Prevents double booking using an atomic conditional UPDATE on the slot status.
    """
    if not doctor_id:
        raise BookingError("Please choose a doctor.")
    reason_text = (reason or "").strip()
    if not reason_text:
        raise BookingError("Please enter a reason for the visit.")

    doctor = db.session.get(Doctor, doctor_id)
    if not doctor:
        raise BookingError("Selected doctor does not exist.")

    try:
        if slot_id is not None:
            slot = db.session.get(Slot, slot_id)
            if not slot or slot.doctor_id != doctor.id:
                raise BookingError("Selected slot is invalid for this doctor.")

            # Atomic re-check & update prevents two concurrent transactions booking the same slot
            updated = (
                db.session.query(Slot)
                .filter(
                    Slot.id == slot.id,
                    Slot.doctor_id == doctor.id,
                    Slot.status == "free",
                )
                .update({"status": "booked"}, synchronize_session=False)
            )
            if updated == 0:
                if waitlist:
                    appt = Appointment(
                        patient_id=patient_id,
                        doctor_id=doctor.id,
                        slot_id=None,
                        reason=f"{reason_text} (Waitlisted for {slot.start_time.strftime('%d %b %I:%M %p')})",
                        status="waitlisted",
                    )
                    db.session.add(appt)
                    db.session.commit()
                    return appt
                raise BookingError("This slot is already booked. Please choose another free slot.")

            appt = Appointment(
                patient_id=patient_id,
                doctor_id=doctor.id,
                slot_id=slot.id,
                reason=reason_text,
                status="requested",
            )
            db.session.add(appt)
            db.session.commit()
            return appt

        # No specific slot provided: check if any free slot exists on target_date (or overall)
        if not waitlist:
            free_query = Slot.query.filter(Slot.doctor_id == doctor.id, Slot.status == "free")
            if target_date is not None:
                day_start = datetime.combine(target_date, time.min)
                day_end = day_start + timedelta(days=1)
                free_query = free_query.filter(Slot.start_time >= day_start, Slot.start_time < day_end)
            if free_query.count() > 0:
                raise BookingError("Please select an available slot.")

        appt = Appointment(
            patient_id=patient_id,
            doctor_id=doctor.id,
            slot_id=None,
            reason=reason_text,
            status="waitlisted",
        )
        db.session.add(appt)
        db.session.commit()
        return appt
    except Exception:
        db.session.rollback()
        raise


def review_appointment(appointment_id):
    """Move a requested appointment into under_review (doctor action)."""
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("Appointment not found.")
    if appt.status != "requested":
        raise BookingError("Only requested appointments can be moved to review.")
    appt.status = "under_review"
    db.session.commit()
    return appt


def confirm_appointment(appointment_id, slot_id=None):
    """Confirm a requested or under_review appointment (doctor only)."""
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("Appointment not found.")
    if appt.status not in ("requested", "under_review"):
        raise BookingError("Only requested or under-review appointments can be confirmed.")

    try:
        if appt.slot_id is None:
            # Assign either the chosen free slot or the earliest free slot for this doctor
            slot_query = Slot.query.filter(Slot.doctor_id == appt.doctor_id, Slot.status == "free")
            if slot_id is not None:
                slot = slot_query.filter(Slot.id == slot_id).first()
            else:
                slot = slot_query.order_by(Slot.start_time.asc()).first()

            if not slot:
                raise BookingError("No free slot available to confirm this appointment.")

            updated = (
                db.session.query(Slot)
                .filter(Slot.id == slot.id, Slot.status == "free")
                .update({"status": "booked"}, synchronize_session=False)
            )
            if updated == 0:
                raise BookingError("Selected slot is no longer free.")
            appt.slot_id = slot.id

        appt.status = "confirmed"
        db.session.commit()
        return appt
    except Exception:
        db.session.rollback()
        raise


def check_in_appointment(appointment_id):
    """Check in a confirmed patient visit (doctor action)."""
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("Appointment not found.")
    if appt.status != "confirmed":
        raise BookingError("Only confirmed appointments can be checked in.")
    appt.status = "visited"
    db.session.commit()
    return appt


def close_appointment(appointment_id):
    """Close a visited appointment when the consultation ends (doctor action)."""
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("Appointment not found.")
    if appt.status != "visited":
        raise BookingError("Only visited appointments can be closed.")
    appt.status = "closed"
    db.session.commit()
    return appt


def cancel_appointment(appointment_id, actor_user):
    """
    Cancel an appointment, free its slot, and promote the oldest waitlisted request
    for the same doctor back to under_review.
    """
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        raise BookingError("Appointment not found.")
    if actor_user.role != "doctor" and appt.patient_id != actor_user.id:
        raise PermissionError("You are not allowed to cancel this appointment.")
    if appt.status in ("visited", "closed", "cancelled"):
        raise BookingError("This appointment can no longer be cancelled.")

    try:
        had_slot = appt.slot_id is not None
        if appt.slot_id is not None:
            slot = db.session.get(Slot, appt.slot_id)
            if slot:
                slot.status = "free"
            appt.slot_id = None

        appt.status = "cancelled"

        promoted = None
        if had_slot:
            promoted = (
                Appointment.query.filter(
                    Appointment.doctor_id == appt.doctor_id,
                    Appointment.status == "waitlisted",
                )
                .order_by(Appointment.created_at.asc(), Appointment.id.asc())
                .first()
            )
            if promoted:
                promoted.status = "under_review"

        db.session.commit()
        return appt, promoted
    except Exception:
        db.session.rollback()
        raise
