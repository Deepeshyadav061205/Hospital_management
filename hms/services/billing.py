import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from models import Bill, Payment, db, utcnow


class BillingError(ValueError):
    """Raised when a billing or payment operation is invalid."""


def create_bill(patient_id, amount, due_date, appointment_id=None):
    """Create a new due bill for a patient."""
    try:
        parsed_amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise BillingError("Please enter a valid bill amount.")
    if parsed_amount <= 0:
        raise BillingError("Bill amount must be greater than zero.")

    bill = Bill(
        patient_id=patient_id,
        appointment_id=appointment_id,
        amount=parsed_amount,
        paid_amount=0.0,
        due_date=due_date,
        status="due",
    )
    db.session.add(bill)
    db.session.commit()
    return bill


def record_payment(bill_id, patient_id, amount):
    """Record a payment against a bill and update its status (due -> partial -> paid)."""
    bill = db.session.get(Bill, bill_id)
    if not bill:
        raise BillingError("Bill not found.")
    if bill.patient_id != patient_id:
        raise PermissionError("You cannot pay another patient's bill.")
    if bill.status == "paid" or bill.balance_due <= 0:
        raise BillingError("This bill is already paid in full.")

    try:
        pay_amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise BillingError("Please enter a valid payment amount.")

    if pay_amount <= 0:
        raise BillingError("Payment amount must be greater than zero.")
    if pay_amount > bill.balance_due + 0.001:
        raise BillingError(f"Payment cannot exceed the remaining balance of Rs. {bill.balance_due:.2f}.")

    payment = Payment(bill_id=bill.id, amount=pay_amount, paid_on=utcnow())
    db.session.add(payment)

    new_paid = round(bill.paid_amount + pay_amount, 2)
    if new_paid >= bill.amount - 0.001:
        bill.paid_amount = round(bill.amount, 2)
        bill.status = "paid"
    elif new_paid > 0:
        bill.paid_amount = new_paid
        bill.status = "partial"
    else:
        bill.paid_amount = 0.0
        bill.status = "due"

    db.session.commit()
    return bill, payment


def generate_receipt_pdf(bill):
    """Generate a clean CityCare Hospital PDF receipt using ReportLab and return bytes."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 60
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "CityCare Hospital")
    pdf.setFont("Helvetica", 11)
    y -= 20
    pdf.drawString(50, y, "Official Billing Receipt")

    y -= 15
    pdf.line(50, y, width - 50, y)

    y -= 28
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Bill / Receipt #: {bill.id}")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(320, y, f"Status: {bill.status.upper()}")

    y -= 20
    pdf.drawString(50, y, f"Patient Name: {bill.patient.name}")
    pdf.drawString(320, y, f"Due Date: {bill.due_date.strftime('%d %b %Y')}")

    y -= 20
    pdf.drawString(50, y, f"Email: {bill.patient.email}")
    pdf.drawString(320, y, f"Phone: {bill.patient.phone or '-'}")

    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Summary")
    y -= 18
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Total Bill Amount: INR {bill.amount:,.2f}")
    y -= 18
    pdf.drawString(50, y, f"Total Paid Amount: INR {bill.paid_amount:,.2f}")
    y -= 18
    pdf.drawString(50, y, f"Balance Due:       INR {bill.balance_due:,.2f}")

    y -= 32
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Payment History")
    y -= 18
    pdf.setFont("Helvetica", 10)
    if bill.payments:
        for idx, pay in enumerate(bill.payments, start=1):
            pdf.drawString(
                50,
                y,
                f"{idx}. Paid on {pay.paid_on.strftime('%d %b %Y %I:%M %p')}  -  INR {pay.amount:,.2f}",
            )
            y -= 16
            if y < 80:
                pdf.showPage()
                y = height - 60
                pdf.setFont("Helvetica", 10)
    else:
        pdf.drawString(50, y, "No payments recorded yet.")

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, 45, "Thank you for choosing CityCare Hospital. This is a computer-generated receipt.")
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
