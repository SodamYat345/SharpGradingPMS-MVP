from app import create_app
from app.extensions import db
from app.models import User, Timesheet, KPI, KPIConfig
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

app = create_app()

roles = [
    ("employee1", "pass123", "employee"),
    ("carp1", "pass123", "carpenter"),
    ("blast1", "pass123", "blaster"),
    ("design1", "pass123", "graphic designer"),
    ("manager1", "pass123", "senior manager"),
    ("super1", "pass123", "supervisor"),
    ("hr1", "pass123", "hr"),
    ("admin1", "adminpass", "admin"),
]

def seed_users():
    for username, password, role in roles:
        if not User.query.filter_by(username=username).first():
            user = User(
                username=username,
                password=generate_password_hash(password),
                role=role
            )
            db.session.add(user)
    db.session.commit()
    print("✅ Users seeded")

def seed_timesheets():
    today = datetime.now().date()
    for user in User.query.filter(User.role.notin_(['admin', 'hr'])):
        for i in range(7):
            day = today - timedelta(days=i)
            start = datetime.combine(day, datetime.strptime("08:15", "%H:%M").time())
            end = datetime.combine(day, datetime.strptime("16:30", "%H:%M").time())
            exists = Timesheet.query.filter_by(employee_id=user.id, clock_in=start).first()
            if not exists:
                ts = Timesheet(
                    employee_id=user.id,
                    clock_in=start,
                    clock_out=end,
                    location="Site Office",
                    latitude=-26.2041,
                    longitude=28.0473
                )
                db.session.add(ts)
    db.session.commit()
    print("✅ Timesheets seeded")

def seed_kpis():
    today = datetime.now().date()
    for user in User.query.filter(User.role.notin_(['admin', 'hr'])):
        configs = KPIConfig.query.filter_by(role=user.role).all()
        for config in configs:
            for offset in range(3):
                kpi_date = today - timedelta(days=offset)
                exists = KPI.query.filter_by(employee_id=user.id, date=kpi_date, kpi_name=config.kpi_name).first()
                if not exists:
                    score = round(random.uniform(60, 95), 2)
                    grade = (
                        "Excellent - A Player" if score >= 85 else
                        "Good - B Player" if score >= 70 else
                        "Average - C Player"
                    )
                    kpi = KPI(
                        employee_id=user.id,
                        kpi_name=config.kpi_name,
                        score=score,
                        weight=config.weight,
                        grade=grade,
                        date=kpi_date,
                        submitted_by="admin"
                    )
                    db.session.add(kpi)
    db.session.commit()
    print("✅ KPIs seeded")

with app.app_context():
    seed_users()
    seed_timesheets()
    seed_kpis()
    print("🎉 Seeding complete.")
