# Sharpshell Performance Management System (PMS)

Sharpshell PMS is a comprehensive performance and attendance management web application built for Sharpshell Engineering. It provides robust modules for KPI tracking, timesheet logging (with geolocation), analytics, and administrative controls, designed to serve employees, supervisors, HR, and managers within an engineering organization.

---

## 🚀 Features

### 🎯 KPI Management
- Role-based KPI templates via `KPIConfig`.
- Weighted KPI entries with auto-graded scores (A–D scale).
- Daily entry restrictions (1 KPI set per user per day).
- Self and supervisor-submitted entries tracked separately.
- Historical KPI view per user.
- Admin/HR dashboard access to all entries and reports.

### ⏱️ Timesheet Tracking
- Daily clock-in / clock-out with location (lat/lon) and optional notes.
- Detection and flagging of:
  - ❗ Late Clock Ins (after 09:15)
  - ❗ Early Clock Outs (before 16:45)
  - ⚠️ Missing Clock Outs
- Daily and historical views for users and supervisors.

### 📊 Advanced Analytics
- Weighted score leaderboard.
- KPI category performance breakdown.
- Submission type trends (employee vs supervisor).
- Underperformance detection (<50% average score).
- Overachiever tracking (based on A-grades).
- KPI volume trends (monthly).
- Time-on-site summaries and averages.
- Attendance anomaly reporting (flags).
- Team comparisons and trends (role-gated).
- Full Chart.js integration for visuals.

### 👤 User Management
- Role-based access (Admin, HR, Supervisor, Employee, Manager).
- `manage_employees` view for HR/Admin/Supervisors to view all staff.
- Profile view and logout from all pages.
- Avatar and responsive nav UX.

---

## 🗂️ Project Structure

SharpGradingPMS-MVP/
├── app/
│ ├── init.py
│ ├── models.py
│ ├── routes.py
│ ├── extensions.py
│ ├── static/
│ └── templates/
├── database/
│ └── pms.sqlite
├── migrations/
├── scripts/
│ └── seed_kpi_configs.py
├── seed_admin.py
├── create_test_users.py
├── requirements.txt
├── run.py
└── README.md


---

## 💻 Technologies Used

- Python 3.13+
- Flask
- Flask-Login
- Flask-Migrate
- SQLite
- SQLAlchemy
- Jinja2
- Tailwind CSS
- Chart.js

---

## ⚙️ Setup Instructions

### 🧪 Local Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/SodamYat345/sharpshell-pms.git
   cd sharpshell-pms

2. Create and activate a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate

3. Install dependencies:
    ```bash
    pip install -r requirements.txt

4. Seed the database:
    ```bash
    python seed_admin.py
    python create_test_users.py

5. Run the app:
    ```bash
    python run.py

6. Visit: http://127.0.0.1:5000

---


## 🔐 Default Credentials

| Role        | Username(s)                         | Password   |
|-------------|-------------------------------------|------------|
| Admin       | `admin`                             | `admin123` |
| Supervisor  | `supervisor`                        | `super123` |
| HR          | `hr1`                               | `pass123`  |
| Manager     | `manager1`                          | `pass123`  |
| Employee    | `employee1`, `carp1`, `blast1`, `design1` | `pass123`  |

___

## 📦 Deployment

Currently optimized for deployment on:

- Render — with run.py as app entry.

- Traditional cPanel hosting (eg Afrihost) via Passenger WSGI (under review).

- PythonAnywhere — basic version supported.

Deployment instructions are available upon request or in the docs/ folder.

___

## 🧠 Credits & Maintainers
Lead Developer: Kudzai Mutanhaurwa (Consultant Dev for Sharpshell Engineering)

___

## 📜 License
This project is released under the MIT License© 2025. While not proprietary and confidential to Sharpshell Engineering, please contact info@sharpshell.co.za for additional usage rights or further collaboration.




