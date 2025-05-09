# scripts/seed_kpi_configs.py

from app import create_app, db
from app.models import KPIConfig

# Default configs
DEFAULT_ROLE_KPIS = {
    "carpenter": {
        "Attendance": 0.25,
        "Punctuality": 0.25,
        "Teamwork": 0.25,
        "Task Completion": 0.25
    },
    "blaster": {
        "Task Completion": 0.3,
        "Initiative": 0.3,
        "Punctuality": 0.2,
        "Teamwork": 0.2
    },
    "graphic designer": {
        "Creativity": 0.4,
        "Task Completion": 0.3,
        "Punctuality": 0.2,
        "Collaboration": 0.1
    },
    "senior manager": {
        "Initiative": 0.3,
        "Leadership": 0.3,
        "Task Completion": 0.2,
        "Teamwork": 0.2
    }
}

def seed_kpis():
    app = create_app()
    with app.app_context():
        for role, kpis in DEFAULT_ROLE_KPIS.items():
            for kpi_name, weight in kpis.items():
                exists = KPIConfig.query.filter_by(role=role, kpi_name=kpi_name).first()
                if not exists:
                    config = KPIConfig(role=role, kpi_name=kpi_name, weight=weight)
                    db.session.add(config)
                    print(f"✅ Added KPI config: {role} - {kpi_name} ({weight})")
        db.session.commit()
        print("✅ All missing KPI configs inserted.")

if __name__ == "__main__":
    seed_kpis()
