from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User, KPI, KPIConfig, Timesheet
from app.extensions import db, login_manager
from sqlalchemy import func
from datetime import datetime, date

main = Blueprint('main', __name__)

# ----- Authentication -----

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/', methods=['GET', 'POST'])
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome, {user.username}', 'success')
            return redirect(url_for('main.dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('main.login'))

# ----- Dashboard -----

@main.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role
    if role == 'admin':
        return render_template('dashboard_admin.html')
    elif role in ['hr', 'supervisor']:
        return render_template('dashboard_hr.html')
    elif role == 'manager':
        return render_template('dashboard_manager.html')
    else:
        return render_template('dashboard.html')

# ----- Profile -----

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# ----- KPI Routes -----

@main.route('/kpi', endpoint="kpi_entry", methods=['GET', 'POST'])
@login_required
def kpi():
    if request.method == 'POST':
        kpi_data = request.form.to_dict(flat=False)
        existing = KPI.query.filter_by(employee_id=current_user.id, date=date.today()).first()
        if existing:
            flash('KPI already submitted for today.', 'warning')
            return redirect(url_for('main.kpi'))

        for name, values in kpi_data.items():
            if name.startswith('kpi_'):
                kpi_name = name[4:]
                score = float(values[0])
                weight = float(request.form.get(f'weight_{kpi_name}', 1))
                grade = 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D'
                new_kpi = KPI(
                    employee_id=current_user.id,
                    kpi_name=kpi_name,
                    score=score,
                    weight=weight,
                    grade=grade,
                    date=date.today(),
                    submitted_by=current_user.username
                )
                db.session.add(new_kpi)
        db.session.commit()
        flash('KPI submitted successfully.', 'success')
        return redirect(url_for('main.kpi'))

    user_kpis = KPIConfig.query.filter_by(role=current_user.role).all()
    return render_template('kpi.html', kpis=user_kpis)

@main.route('/kpi-history')
@login_required
def kpi_history():
    history = KPI.query.filter_by(employee_id=current_user.id).order_by(KPI.date.desc()).all()
    return render_template('kpi_history.html', history=history)

# ----- Reports -----

@main.route('/view-reports')
@login_required
def view_reports():
    all_kpis = KPI.query.order_by(KPI.date.desc()).all()
    return render_template('view_reports.html', kpis=all_kpis)

# ----- Timesheets -----

@main.route('/timesheet', methods=['GET', 'POST'])
@login_required
def timesheet():
    if request.method == 'POST':
        clock_type = request.form.get('clock_type')
        location = request.form.get('location')
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')

        if clock_type == 'in':
            clock_in = Timesheet(
                employee_id=current_user.id,
                clock_in=datetime.now(),
                location=location,
                latitude=lat,
                longitude=lon
            )
            db.session.add(clock_in)
            db.session.commit()
            flash('✅ Clocked in successfully!', 'success')
        elif clock_type == 'out':
            latest = Timesheet.query.filter_by(employee_id=current_user.id).order_by(Timesheet.id.desc()).first()
            if latest and not latest.clock_out:
                latest.clock_out = datetime.now()
                db.session.commit()
                flash('✅ Clocked out successfully!', 'info')
            else:
                flash('⚠️ No active clock-in record found.', 'warning')
        return redirect(url_for('main.timesheet'))

    today = Timesheet.query.filter_by(employee_id=current_user.id).order_by(Timesheet.id.desc()).first()
    return render_template('timesheets/timesheet.html', today=today)

@main.route('/timesheets/daily')
@login_required
def daily_timesheet():
    today = date.today()
    entries = Timesheet.query.filter(
        Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
    ).order_by(Timesheet.clock_in.asc()).all()
    return render_template('timesheets/daily_timesheet.html', entries=entries)

@main.route('/my-timesheet-history')
@login_required
def my_timesheet_history():
    records = Timesheet.query.filter_by(employee_id=current_user.id).order_by(Timesheet.clock_in.desc()).all()
    return render_template('timesheets/my_timesheet_history.html', records=records)

@main.route('/team-timesheets')
@login_required
def team_timesheets():
    if current_user.role not in ['supervisor', 'manager', 'hr', 'admin']:
        return redirect(url_for('main.unauthorized_timesheet'))

    all_records = Timesheet.query.order_by(Timesheet.clock_in.desc()).all()
    return render_template('timesheets/team_timesheets.html', records=all_records)

@main.route('/unauthorized-timesheet')
@login_required
def unauthorized_timesheet():
    return render_template('unauthorized_timesheet.html')

@main.route('/view-employee-timesheet/<int:employee_id>')
@login_required
def view_employee_timesheet(employee_id):
    if current_user.role not in ['supervisor', 'manager', 'hr', 'admin']:
        return redirect(url_for('main.unauthorized_timesheet'))

    records = Timesheet.query.filter_by(employee_id=employee_id).order_by(Timesheet.clock_in.desc()).all()
    return render_template('timesheets/view_employee_timesheet.html', records=records)

# ----- Analytics Views -----

def role_required(roles):
    if current_user.role not in roles:
        return redirect(url_for('main.dashboard'))

@main.route('/analytics/weighted-scores')
@login_required
def weighted_scores():
    return role_required(['hr', 'admin', 'manager']) or render_template('analytics/weighted_scores.html')

@main.route('/analytics/underperformance')
@login_required
def underperformance():
    return role_required(['hr', 'admin', 'manager']) or render_template('analytics/underperformance.html')

@main.route('/analytics/kpi-volume')
@login_required
def kpi_volume():
    return role_required(['hr', 'admin']) or render_template('analytics/kpi_volume.html')

@main.route('/analytics/submission-type-breakdown')
@login_required
def submission_type_breakdown():
    return role_required(['hr', 'admin']) or render_template('analytics/submission_type_breakdown.html')

@main.route('/analytics/category-breakdown')
@login_required
def category_breakdown():
    return role_required(['hr', 'admin']) or render_template('analytics/category_breakdown.html')

@main.route('/analytics/weighting-impact')
@login_required
def weighting_impact():
    return role_required(['hr', 'admin']) or render_template('analytics/weighting_impact.html')

@main.route('/analytics/overachievers')
@login_required
def overachievers():
    return role_required(['hr', 'admin', 'manager']) or render_template('analytics/overachievers.html')

@main.route('/analytics/timesheet-summary')
@login_required
def timesheet_summary():
    return role_required(['hr', 'admin']) or render_template('analytics/timesheet_summary.html')

@main.route('/analytics/attendance-flags')
@login_required
def attendance_flags():
    return role_required(['hr', 'admin']) or render_template('analytics/attendance_flags.html')

@main.route('/analytics/team-comparisons')
@login_required
def team_comparisons():
    return role_required(['manager', 'admin']) or render_template('team_comparisons.html')

@main.route('/analytics/kpi-trends')
@login_required
def kpi_trends():
    return role_required(['manager', 'admin']) or render_template('analytics/kpi_trends.html')

# ----- Employee Management -----

@main.route('/manage_employees')
@login_required
def manage_employees():
    if current_user.role not in ['admin', 'hr', 'supervisor', 'manager']:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.dashboard'))

    employees = User.query.filter(User.role != 'admin').order_by(User.username.asc()).all()
    return render_template('manage_employees.html', employees=employees)
