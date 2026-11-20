# 🏥 CityCare Hospital — Hospital Management System (HMS)

A clean, full-stack **Hospital Management System & Public Hospital Finder** built with **Python 3, Flask, Flask-SQLAlchemy, Jinja2, Leaflet.js, ReportLab, and pytest**. It combines an unauthenticated public hospital/bed/ICU/blood-bank locator across 10 Indian cities with role-based **Patient** and **Doctor** portals.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-0B3C49?style=flat-square&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/Flask--SQLAlchemy-3.1+-0F8B8D?style=flat-square)
![Leaflet](https://img.shields.io/badge/Leaflet-1.9.4-199900?style=flat-square&logo=leaflet&logoColor=white)
![ReportLab](https://img.shields.io/badge/ReportLab-PDF%20Receipts-4B5563?style=flat-square)
![Pytest](https://img.shields.io/badge/Tests-13%20Passing-0E6B52?style=flat-square&logo=pytest&logoColor=white)

---

## 📸 Project Screenshots

### 1. Public Hospital Finder & Interactive Map (`/hospitals`)
Browse all 10 cities on an interactive OpenStreetMap view with hospital markers and quick-navigation city cards.

![Public Hospital Finder](docs/screenshots/hospital_finder.png)

### 2. City View Sorted by Distance (`/hospitals/city/Jaipur`)
Hospitals sorted by pure-Python Haversine distance (km) from the city center, highlighting low ICU (`<= 10%`) and low blood stock (`< 5` units) in coral.

![Jaipur Hospitals](docs/screenshots/city_jaipur.png)

### 3. Hospital Detail & Blood Bank Table (`/hospitals/<id>`)
Full contact info, live beds & ICU counters, 8-group blood stock table, map pin, doctors list, and direct appointment booking.

![Hospital Detail](docs/screenshots/hospital_detail.png)

### 4. Patient Portal & Slot Booking (`/patient/dashboard`, `/patient/book`)
Patients view active appointments, pending bills, medical records, and book free time slots or join a waitlist.

| Patient Dashboard | Book Appointment |
| :---: | :---: |
| ![Patient Dashboard](docs/screenshots/patient_dashboard.png) | ![Book Appointment](docs/screenshots/book_appointment.png) |

### 5. Doctor Hospital Availability Editor (`/doctor/hospital`) & Login (`/login`)
Doctors update live beds, ICU capacity, and blood bank units with validation (`0 <= available <= total`), reflected immediately on public pages.

| Doctor Availability Editor | Login Portal |
| :---: | :---: |
| ![Doctor Hospital Editor](docs/screenshots/doctor_hospital.png) | ![Login Page](docs/screenshots/login.png) |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3, Flask 3 | Application factory, blueprints, session auth, CSRF protection |
| **ORM & Database** | Flask-SQLAlchemy, SQLite (`hms.db`) / MySQL (`PyMySQL`) | Relational models, atomic slot updates, zero-config SQLite default or `DATABASE_URL` |
| **Templating & UI** | Jinja2, Custom CSS (`style.css`), Vanilla JS (`main.js`) | Responsive teal & coral medical UI with mobile navbar toggle, zero frontend frameworks |
| **Maps & Geolocation** | Leaflet `1.9.4` (cdnjs) + OpenStreetMap + Pure-Python Haversine | Interactive city/hospital maps and straight-line distance ranking without GIS libraries |
| **PDF Generation** | ReportLab | Downloadable itemized PDF billing receipts |
| **Security** | Werkzeug (`generate_password_hash` / `check_password_hash`), HMAC CSRF tokens | Password hashing, CSRF checks on all `POST` forms, strict RBAC & ownership checks |
| **Testing** | pytest | Automated test suite covering concurrency/waitlist, RBAC, billing, PDFs, geo & validation |

---

## ✨ Features

### 🌍 Public Hospital Finder (No Login Required)
- **`/hospitals`** — Responsive grid of 10 city cards and an interactive map displaying all 20 hospitals.
- **`/hospitals/city/<city_name>`** — Hospitals sorted by ascending Haversine distance (`km`, 1 decimal place) from the city center with live beds, ICU, and 8 blood group chips (`A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`).
- **`/hospitals/<id>`** — Address, phone, bed/ICU counts, blood bank availability table, map pin, doctors list, and direct **Book appointment** shortcut for logged-in patients.
- **Low-Availability Alerts** — Beds/ICU at `<= 10%` of total and blood units `< 5` are automatically flagged in coral (`#E85D4A`).

### 🧑‍⚕️ Patient Portal (`/patient/*`)
- **Dashboard** — Summary cards for active appointments, total balance due (`₹`), medical records, pending labs, and hospital notices.
- **Atomic Slot Booking** — Pick a doctor and date, select a free 30-minute slot (re-checked atomically in a DB transaction to prevent double booking), or join the waitlist when full.
- **Cancellation & Auto-Promotion** — Cancelling an appointment frees the slot and promotes the oldest waitlisted request for that doctor to `under_review`.
- **Billing & PDF Receipts** — Record partial or full payments (`due` → `partial` → `paid`) and download **ReportLab PDF receipts**.
- **Medical Records & Lab Tests** — Inspect diagnoses/prescriptions and submit lab test requests.

### 🩺 Doctor Portal (`/doctor/*`)
- **Dashboard** — Today's appointments, upcoming confirmed visits, pending bills, open requests, and pending lab tests.
- **Appointment Workflow** — Transition bookings through `requested` → `under_review` → `confirmed` → `visited` → `closed` (or reject/cancel).
- **Patient Directory & Clinical Notes** — Search patients, add medical records/prescriptions, issue bills, approve lab tests, and publish lab findings.
- **Live Hospital Availability (`/doctor/hospital`)** — Update beds, ICU capacity, and all 8 blood groups with strict validation (`0 <= available <= total`, `units >= 0`). Returns `403 Forbidden` for patients.

---

## 📁 Project Structure

```text
hospital_management/
├── docs/
│   └── screenshots/              # Rendered application screenshots
├── hms/
│   ├── app.py                    # create_app factory, CSRF hook, error handlers, auto-seed
│   ├── config.py                 # SQLite default & DATABASE_URL (MySQL) configuration
│   ├── models.py                 # City, Hospital, BloodStock, User, Doctor, Slot, Appointment, Bill, Payment, Record, LabTest, Notice
│   ├── seed.py                   # Idempotent seed script (10 cities, 20 hospitals, doctors, patients, slots, bills, records, notices)
│   ├── requirements.txt
│   ├── routes/
│   │   ├── auth.py               # Login, register, logout, role_required decorator
│   │   ├── hospitals.py          # Public /hospitals, /hospitals/city/<name>, /hospitals/<id>
│   │   ├── patient.py            # Patient dashboard, booking, bills, PDF receipts, records, notices
│   │   └── doctor.py             # Doctor dashboard, requests, patients, reports, /doctor/hospital
│   ├── services/
│   │   ├── appointments.py       # Atomic slot booking, waitlist promotion, status transitions
│   │   ├── billing.py            # Bill creation, payment recording, ReportLab PDF generator
│   │   ├── hospitals.py          # Pure-Python haversine_km, nearest_hospitals, low_stock, availability validation
│   │   └── records.py            # Medical records & lab test workflow
│   ├── static/
│   │   ├── css/style.css         # Responsive hospital theme (deep teal #0B3C49, teal #0F8B8D, coral #E85D4A)
│   │   └── js/main.js            # Mobile menu toggle, slot selection, confirmation dialogs, Leaflet map init
│   ├── templates/                # Jinja2 templates (base, auth, hospitals/*, patient/*, doctor/*)
│   └── tests/
│       └── test_core.py          # 13 pytest tests for booking, RBAC, billing, PDFs, geo, availability
└── README.md
```

---

## 🗺️ Seeded Cities & Hospitals

Each city is seeded with **`{City} Lifeline Hospital`** and **`{City} Sanjeevani Hospital`** located 2–6 km from the city center:

| City | State | Coordinates (`lat, lng`) |
| :--- | :--- | :--- |
| **Jaipur** | Rajasthan | `26.9124, 75.7873` |
| **Delhi** | Delhi | `28.6139, 77.2090` |
| **Mumbai** | Maharashtra | `19.0760, 72.8777` |
| **Bengaluru** | Karnataka | `12.9716, 77.5946` |
| **Chennai** | Tamil Nadu | `13.0827, 80.2707` |
| **Kolkata** | West Bengal | `22.5726, 88.3639` |
| **Hyderabad** | Telangana | `17.3850, 78.4867` |
| **Pune** | Maharashtra | `18.5204, 73.8567` |
| **Ahmedabad** | Gujarat | `23.0225, 72.5714` |
| **Lucknow** | Uttar Pradesh | `26.8467, 80.9462` |

> **Demo Alert State:** `Jaipur Sanjeevani Hospital` is seeded with `0` available ICU beds and `2` units of `O-` blood so coral low-availability alerts are visible immediately.

---

## 🚀 Setup & Run

### 1. Run with SQLite (Default)

```bash
cd hms
pip install -r requirements.txt
python seed.py
flask --app app run
```

Open **http://127.0.0.1:5000** (or **http://127.0.0.1:5000/hospitals** for the public finder).
*(If upgrading from an older schema, delete `hms/hms.db` before running `python seed.py`.)*

### 2. Switch from SQLite to MySQL

```bash
# 1. Create an empty database in MySQL: CREATE DATABASE hms;
export DATABASE_URL="mysql+pymysql://user:pass@localhost/hms"
cd hms
python seed.py
flask --app app run
```

---

## 🔑 Test Login Credentials

| Role | Name | Email | Password | Assigned Hospital |
| :--- | :--- | :--- | :--- | :--- |
| **Doctor** (Cardiology) | Dr. Mehta | `mehta@citycare.com` | `Doctor@123` | Jaipur Lifeline Hospital |
| **Doctor** (General Medicine) | Dr. Rao | `rao@citycare.com` | `Doctor@123` | Jaipur Sanjeevani Hospital |
| **Patient** | Aman Verma | `aman@example.com` | `Patient@123` | — |
| **Patient** | Neha Singh | `neha@example.com` | `Patient@123` | — |
| **Patient** | Rahul Sharma | `rahul@example.com` | `Patient@123` | — |
| **Patient** | Priya Jain | `priya@example.com` | `Patient@123` | — |

---

## 🧪 Running Tests

```bash
cd hms
pytest -q
```

All **13 tests** in `hms/tests/test_core.py` verify:
- Preventing double-booking on the same slot
- Creating waitlisted requests when slots are full
- Promoting the oldest waitlisted request upon cancellation
- `403` enforcement for patients on doctor routes (`/doctor/*` including `/doctor/hospital`)
- Object-level isolation on patient bills, PDF receipts, and medical records
- Bill status transitions (`due` → `partial` → `paid`) and non-zero ReportLab PDF generation
- Pure-Python Haversine distance (`Jaipur`–`Delhi` in 220–250 km) and sorted `nearest_hospitals("Jaipur")`
- Unauthenticated public access (`200`) to `/hospitals` and `/hospitals/city/Jaipur`
- Doctor hospital availability updates & validation (`available_beds > total_beds` rejected)
- Low-stock coral flagging for `Jaipur Sanjeevani Hospital` (`ICU` and `O-`)
