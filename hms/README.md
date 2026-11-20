# CityCare Hospital — Hospital Management System (HMS)

A simple, clean college-project web application built with **Python 3, Flask, Flask-SQLAlchemy, Jinja2, Leaflet.js, ReportLab, and pytest**.

## Features

- **Public Hospital Finder & Interactive Map (No Login Required)**
  - `/hospitals` — Browse all 10 cities and explore every hospital on an interactive Leaflet + OpenStreetMap view.
  - `/hospitals/city/<city>` — View hospitals in a city sorted by straight-line Haversine distance (km) from the city center, with live beds, ICU, and blood bank chips (low ICU/beds &le; 10% and blood units &lt; 5 highlighted in coral).
  - `/hospitals/<id>` — Full hospital details, blood stock table, map pin, doctors list, and direct appointment booking for logged-in patients.
- **Authentication & Role-Based Access**
  - Password hashing with Werkzeug (`generate_password_hash` / `check_password_hash`)
  - Session-based authentication and CSRF token protection on all `POST` forms
  - Strict role separation (`403 Forbidden` for patients accessing doctor routes, and object-level checks so patients can never view another patient's bills, receipts, or records)
- **Patient Portal**
  - Dashboard with active appointments, pending bill totals, records count, and latest notices
  - Appointment booking by doctor and date with atomic DB transaction checks (prevents double booking) and automatic waitlisting when slots are full
  - Appointment status tracking and cancellation (automatically frees the slot and promotes the oldest waitlisted request to `under_review`)
  - Billing summary, payment recording (`due` -> `partial` -> `paid`), and downloadable **ReportLab PDF receipts**
  - Medical records viewer and lab test request submission
  - Hospital notice board
- **Doctor Portal**
  - Dashboard with today's appointments, upcoming visits, pending bills count, and open requests
  - Appointment request workflow (`requested` -> `under_review` -> `confirmed` -> `visited` -> `closed`, or `reject/cancel`)
  - Searchable patient directory and detailed patient view
  - Add medical records & prescriptions, create bills, approve lab tests, and enter lab report findings
  - `/doctor/hospital` — Edit the doctor's own hospital beds, ICU counts, and blood units with validation (`0 <= available <= total`, `units >= 0`)

## Pages

- Public: `/hospitals`, `/hospitals/city/<city>`, `/hospitals/<id>`, `/login`, `/register`
- Patient: `/patient/dashboard`, `/patient/book`, `/patient/appointments`, `/patient/bills`, `/patient/bills/<id>`, `/patient/records`, `/patient/records/<id>`, `/patient/notices`
- Doctor: `/doctor/dashboard`, `/doctor/requests`, `/doctor/patients`, `/doctor/patients/<id>`, `/doctor/reports`, `/doctor/hospital`

## Cities Included in Seed Data

1. Jaipur (Rajasthan)
2. Delhi (Delhi)
3. Mumbai (Maharashtra)
4. Bengaluru (Karnataka)
5. Chennai (Tamil Nadu)
6. Kolkata (West Bengal)
7. Hyderabad (Telangana)
8. Pune (Maharashtra)
9. Ahmedabad (Gujarat)
10. Lucknow (Uttar Pradesh)

Each city includes `{City} Lifeline Hospital` and `{City} Sanjeevani Hospital`.

## Editing Hospital Availability Data

1. Log in as a doctor (for example, `mehta@citycare.com` or `rao@citycare.com`).
2. Click **My Hospital** in the top navigation bar (`/doctor/hospital`).
3. Update Available/Total Beds, Available/Total ICU Beds, and Blood Stock units (`A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`).
4. Click **Save Availability**. Validation enforces `0 <= available <= total` and non-negative blood units. Updates immediately appear on the public `/hospitals` pages.

## Setup & Run (SQLite Default)

```bash
cd hms
pip install -r requirements.txt
python seed.py
flask --app app run
```

If upgrading from an older schema, delete the existing `hms.db` before running `python seed.py`.
Open `http://127.0.0.1:5000` in your browser.
*(Note: `app.py` also initializes and seeds the database automatically on startup if it is empty.)*

## Switching from SQLite to MySQL

By default, the app uses a local SQLite database (`hms.db`). To use MySQL instead:

1. Create an empty MySQL database (for example, `CREATE DATABASE hms;`).
2. Set the `DATABASE_URL` environment variable before running `seed.py` or `flask`:

```bash
export DATABASE_URL="mysql+pymysql://user:pass@localhost/hms"
python seed.py
flask --app app run
```

## Test Login Credentials

| Role | Name | Email | Password | Hospital |
| :--- | :--- | :--- | :--- | :--- |
| Doctor (Cardiology) | Dr. Mehta | `mehta@citycare.com` | `Doctor@123` | Jaipur Lifeline Hospital |
| Doctor (General Medicine) | Dr. Rao | `rao@citycare.com` | `Doctor@123` | Jaipur Sanjeevani Hospital |
| Patient | Aman Verma | `aman@example.com` | `Patient@123` | — |
| Patient | Neha Singh | `neha@example.com` | `Patient@123` | — |
| Patient | Rahul Sharma | `rahul@example.com` | `Patient@123` | — |
| Patient | Priya Jain | `priya@example.com` | `Patient@123` | — |

## Running Tests

```bash
cd hms
pytest -q
```
