from app.extensions import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'admin', 'supervisor', 'employee', etc.

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100))
    role = db.Column(db.String(100))

class Timesheet(db.Model):
    __table_args__ = {'extend_existing': True}  # ✅ Fix for existing table error
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    employee = db.relationship('User', backref='timesheets')
    clock_in = db.Column(db.DateTime)
    clock_out = db.Column(db.DateTime)
    location = db.Column(db.String(150))  # Optional text field
    latitude = db.Column(db.Float)        # ✅ Geo latitude
    longitude = db.Column(db.Float)       # ✅ Geo longitude

class KPI(db.Model):
    __table_args__ = {'extend_existing': True}  # ✅ Fix for existing table error
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    kpi_name = db.Column(db.String(100))
    score = db.Column(db.Float)
    weight = db.Column(db.Float)
    grade = db.Column(db.String(20))
    date = db.Column(db.Date)
    submitted_by = db.Column(db.String(150))  # ✅ New field to track who submitted it: username or role

class KPIConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(100), nullable=False)
    kpi_name = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)
