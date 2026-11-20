from models import LabTest, Record, db


class RecordError(ValueError):
    """Raised when a medical record or lab test operation is invalid."""


def create_record(patient_id, doctor_id, diagnosis, prescription, status="open"):
    """Create a new medical record and prescription for a patient."""
    diag = (diagnosis or "").strip()
    rx = (prescription or "").strip()
    if not diag:
        raise RecordError("Diagnosis is required.")
    if not rx:
        raise RecordError("Prescription is required.")
    if status not in ("open", "closed"):
        status = "open"

    record = Record(
        patient_id=patient_id,
        doctor_id=doctor_id,
        diagnosis=diag,
        prescription=rx,
        status=status,
    )
    db.session.add(record)
    db.session.commit()
    return record


def close_record(record_id):
    """Mark an open medical record as closed."""
    record = db.session.get(Record, record_id)
    if not record:
        raise RecordError("Record not found.")
    record.status = "closed"
    db.session.commit()
    return record


def request_lab_test(patient_id, test_name, record_id=None):
    """Allow a patient to request a lab test."""
    name = (test_name or "").strip()
    if not name:
        raise RecordError("Please enter the lab test name.")

    if record_id is not None:
        record = db.session.get(Record, record_id)
        if not record or record.patient_id != patient_id:
            raise RecordError("Invalid medical record selected.")

    test = LabTest(
        patient_id=patient_id,
        record_id=record_id,
        test_name=name,
        status="requested",
        report_text="",
    )
    db.session.add(test)
    db.session.commit()
    return test


def approve_lab_test(test_id):
    """Approve a requested lab test (doctor action)."""
    test = db.session.get(LabTest, test_id)
    if not test:
        raise RecordError("Lab test not found.")
    if test.status != "requested":
        raise RecordError("Only requested lab tests can be approved.")
    test.status = "approved"
    db.session.commit()
    return test


def complete_lab_test(test_id, report_text):
    """Save report findings and mark an approved lab test as completed (doctor action)."""
    test = db.session.get(LabTest, test_id)
    if not test:
        raise RecordError("Lab test not found.")
    if test.status not in ("approved", "requested"):
        raise RecordError("This lab test is already completed.")
    text = (report_text or "").strip()
    if not text:
        raise RecordError("Please enter the lab report findings.")
    test.report_text = text
    test.status = "completed"
    db.session.commit()
    return test
