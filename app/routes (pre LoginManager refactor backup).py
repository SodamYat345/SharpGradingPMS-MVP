'''
from flask import Blueprint, render_template, redirect, url_for, request, session, jsonify
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from app.extensions import db
from app.models import User, KPI, Timesheet, KPIConfig
from collections import defaultdict, Counter
from sqlalchemy import func
from flask_login import LoginManager, login_user, logout_user, current_user #login_required

main = Blueprint('main', __name__)

# Role-based KPI configurations
# Define the KPI sets for each role. This should be a dictionary where the keys are the role names and the values are dictionaries of KPIs and their weights. The weights should sum up to 1 for each role.

ROLE_KPI_SETS = {
    "employee": {
        "Punctuality": 0.3,
        "Task Completion": 0.4,
        "Teamwork": 0.3
    },
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

TIMESHEET_ROLES = ['employee', 'carpenter', 'blaster', 'graphic designer']

@main.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    # Initialize Flask-Login    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            #session['user_id'] = user.id
            #session['role'] = user.role
            #session['username'] = user.username
            login_user(user)
            return redirect(url_for('main.dashboard'))
        return render_template('login.html', error='Invalid credentials', datetime=datetime)
    return render_template('login.html', datetime=datetime, hide_nav=True)

@main.route('/dashboard')
#@login_required
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user = User.query.get(session['user_id'])
    session['role'] = user.role
    session['username'] = user.username

    # HR-style dashboard for hr and supervisor-type users
    if user.role in ['hr', 'supervisor', 'supervisor1']:
        return render_template('dashboard_hr.html', username=user.username, role=user.role)

    # Manager-style dashboard
    elif user.role == 'senior manager':
        return render_template('dashboard_manager.html', username=user.username, role=user.role)
    
    # Admin-style dashboard
    elif user.role == 'admin':
        return render_template('dashboard_admin.html', username=user.username, role=user.role)

    # Default employee-style dashboard
    return render_template('dashboard.html', username=user.username, role=user.role)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


@main.route('/timesheet', methods=['GET', 'POST'])
def timesheet():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    if session.get('role').lower() not in TIMESHEET_ROLES:
        render_template('unauthorized_timesheet.html'), 403
    
    # Get the current user ID and today's date
    user_id = session['user_id']
    today = date.today()
    message = ""
    action = None

    entry = Timesheet.query.filter(
        Timesheet.employee_id == user_id,
        Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
    ).order_by(Timesheet.id.desc()).first()

    if request.method == 'POST':
        now = datetime.now()
        location = request.form['location']
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not entry:
            new_entry = Timesheet(
                employee_id=user_id,
                clock_in=now,
                location=location,
                latitude=latitude,
                longitude=longitude
            )
            db.session.add(new_entry)
            db.session.commit()
            message = "✅ Clocked in successfully!"
        elif not entry.clock_out:
            entry.clock_out = now
            entry.latitude = latitude
            entry.longitude = longitude
            db.session.commit()
            message = "✅ Clocked out successfully!"
        else:
            message = "✔️ You have already clocked out today."

        return redirect(url_for('main.timesheet'))

    if not entry:
        action = 'clock_in'
    elif entry and not entry.clock_out:
        action = 'clock_out'
    else:
        action = 'done'

    return render_template('timesheets/timesheet.html', action=action, message=message, entry=entry)

# Updated /kpi route with all fixes and restrictions implemented
@main.route('/kpi', methods=['GET', 'POST'])
def kpi_entry():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    user_id = session['user_id']
    username = session.get('username')
    is_supervisor = role in ['supervisor', 'hr', 'senior manager', 'admin']

    employees = []
    selected_user = None
    kpi_configs = []
    message = ""

    if is_supervisor:
        employees = User.query.filter(User.role.notin_(['admin', 'hr', 'supervisor'])).all()

        # Handle POST submission or default to first employee on GET
        if request.method == 'POST' and 'employee_id' in request.form:
            selected_user_id = int(request.form.get('employee_id'))
            selected_user = User.query.get(selected_user_id)
        elif employees:
            selected_user = employees[0]  # default selection on GET if list not empty
    else:
        selected_user = User.query.get(user_id)

    if not selected_user:
        return render_template('error.html', message="❌ No employee selected or available."), 400

    selected_role = selected_user.role.lower()
    kpi_configs = KPIConfig.query.filter_by(role=selected_role).all()

    if not kpi_configs:
        return render_template('error.html', message=f"❌ No KPI configuration found for role: {selected_role}"), 400

    # Handle KPI submission
    if request.method == 'POST' and 'kpi_name' in request.form and request.form.get('score'):
        
        try:
            score = float(request.form['score'])
        except ValueError:
            message = "⚠️ Invalid score submitted."
            return render_template(
                'kpi.html',
                message=message,
                kpi_options={cfg.kpi_name: cfg.weight for cfg in kpi_configs},
                employees=employees,
                is_supervisor=is_supervisor,
                selected_user=selected_user
            )
        kpi_name = request.form['kpi_name']
        
        # Check if the KPI has already been submitted today
        existing_kpi = KPI.query.filter_by(
            employee_id=selected_user.id,
            date=date.today(),
            kpi_name=kpi_name
        ).first()

        if existing_kpi:
            message = f"⚠️ {selected_user.username} has already submitted '{kpi_name}' KPI today."
        else:
            config = next((cfg for cfg in kpi_configs if cfg.kpi_name == kpi_name), None)
            weight = config.weight if config else 0.0
            grade = (
                "Excellent - A Player" if score >= 85 else
                "Good - B Player" if score >= 70 else
                "Average - C Player" if score >= 50 else
                "Poor - D Player"
            )

            new_kpi = KPI(
                employee_id=selected_user.id,
                kpi_name=kpi_name,
                score=score,
                weight=weight,
                grade=grade,
                date=date.today(),
                submitted_by=username
            )
            db.session.add(new_kpi)
            db.session.commit()
            message = f"✅ KPI submitted for {selected_user.username}: {kpi_name} — Grade: {grade}"

    return render_template(
        'kpi.html',
        message=message,
        kpi_options={cfg.kpi_name: cfg.weight for cfg in kpi_configs},
        employees=employees,
        is_supervisor=is_supervisor,
        selected_user=selected_user
    )

@main.route('/kpi/history')
def kpi_history():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    username = session['username']

    # Get all KPI entries for the current user
    all_kpis = KPI.query.filter_by(employee_id=user_id).order_by(KPI.date.desc()).all()

    # Split them into supervisor- and self-submitted
    supervisor_kpis = [k for k in all_kpis if k.submitted_by != username]
    self_kpis = [k for k in all_kpis if k.submitted_by == username]

    # Show all for the table
    kpis = all_kpis

    # Use supervisor KPIs for charts if available, else fallback to self-submitted
    kpi_source = supervisor_kpis if supervisor_kpis else self_kpis

    # Prepare data for charts
    kpi_data = [
        {
            "date": k.date.strftime("%Y-%m-%d"),
            "kpi_name": k.kpi_name,
            "score": k.score,
            "weight": k.weight,
            "grade": k.grade,
            "submitted_by": k.submitted_by
        }
        for k in kpi_source
    ]

    return render_template('kpi_history.html', kpis=kpis, kpi_data=kpi_data, current_user=username)

@main.route('/view-reports')
def view_reports():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    kpis = KPI.query.order_by(KPI.date.desc()).all()

    # Convert to dict for chart use
    kpi_data = [
        {
            "date": kpi.date.strftime('%Y-%m-%d'),
            "employee_id": kpi.employee_id,
            "kpi_name": kpi.kpi_name,
            "score": kpi.score,
            "weight": kpi.weight,
            "grade": kpi.grade,
            "submitted_by": kpi.submitted_by
        }
        for kpi in kpis
    ]

    return render_template("view_reports.html", kpis=kpis, kpi_data=kpi_data)

@main.route('/manage_employees')
#@login_required
def manage_employees():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role', '').lower()

    # ✅ Include senior manager
    if role not in ['admin', 'hr', 'supervisor', 'manager', 'senior manager']:
        return render_template('error.html', message="❌ You are not authorized to access this page."), 403

    employees = User.query.filter(User.role.notin_([
        'admin', 'hr', 'supervisor', 'manager', 'senior manager'
    ])).all()

    return render_template('manage_employees.html', employees=employees)

@main.route('/analytics/kpi-trends')
def kpi_trends():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    username = session.get('username')
    user_id = session.get('user_id')

    all_kpis = KPI.query.filter_by(employee_id=user_id).order_by(KPI.date.asc()).all()
    supervisor_kpis = [k for k in all_kpis if k.submitted_by != username]
    self_kpis = [k for k in all_kpis if k.submitted_by == username]

    def format_kpis(kpi_list):
        return [
            {
                "date": k.date.strftime('%Y-%m-%d'),
                "score": k.score,
                "kpi_name": k.kpi_name
            } for k in kpi_list
        ]

    return render_template(
        'analytics/kpi_trends.html',
        chart_data=format_kpis(supervisor_kpis),
        fallback_data=format_kpis(self_kpis),
        has_supervisor_data=len(supervisor_kpis) > 0,
        has_self_data=len(self_kpis) > 0
    )

@main.route('/analytics/team-comparisons')
def team_comparisons():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    from sqlalchemy.sql import func
    # Get all KPIs submitted by supervisors/HR
    supervisor_kpis = KPI.query.filter(KPI.submitted_by != session.get('username')).all()

    # Aggregate KPI scores by role and category
    role_kpi_data = {}
    for kpi in supervisor_kpis:
        user = User.query.get(kpi.employee_id)
        if not user:
            continue
        role = user.role.title()
        role_kpi_data.setdefault(role, {})
        role_kpi_data[role].setdefault(kpi.kpi_name, []).append(kpi.score)

    # Prepare data for charts
    avg_role_scores = {}  # overall per role
    category_scores = {}  # per category per role

    for role, kpis in role_kpi_data.items():
        all_scores = []
        for kpi_name, scores in kpis.items():
            avg_score = sum(scores) / len(scores)
            all_scores.extend(scores)
            category_scores.setdefault(kpi_name, {})[role] = avg_score
        avg_role_scores[role] = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0

    return render_template(
        'team_comparisons.html',
        avg_role_scores=avg_role_scores,
        category_scores=category_scores
    )

@main.route('/analytics/category-breakdown')
def category_breakdown():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role', '').lower()
    user_id = session['user_id']

    if role in ['admin', 'hr', 'supervisor', 'senior manager']:
        # View for all employees
        kpis = KPI.query.all()
    else:
        # Restrict to current user
        kpis = KPI.query.filter_by(employee_id=user_id).all()

    category_totals = {}
    category_counts = {}

    for k in kpis:
        category_totals[k.kpi_name] = category_totals.get(k.kpi_name, 0) + k.score
        category_counts[k.kpi_name] = category_counts.get(k.kpi_name, 0) + 1

    avg_scores = {
        name: round(category_totals[name] / category_counts[name], 2)
        for name in category_totals
    }

    return render_template('analytics/category_breakdown.html', avg_scores=avg_scores)

@main.route('/analytics/weighted-scores')
def weighted_scores():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    # Fetch only supervisor-submitted KPIs for analytics integrity
    username = session.get('username')
    supervisor_kpis = KPI.query.filter(KPI.submitted_by != username).all()

    # Group weighted scores by employee
    scores_by_user = {}
    counts_by_user = {}
    for k in supervisor_kpis:
        uid = k.employee_id
        weighted = k.score * k.weight
        scores_by_user.setdefault(uid, 0)
        counts_by_user.setdefault(uid, 0)
        scores_by_user[uid] += weighted
        counts_by_user[uid] += 1

    # Compute average weighted score per user
    leaderboard = []
    for uid, total_wscore in scores_by_user.items():
        count = counts_by_user[uid]
        avg_w = round(total_wscore / count, 2) if count else 0
        user = User.query.get(uid)
        leaderboard.append({
            'username': user.username if user else f'User {uid}',
            'avg_weighted_score': avg_w
        })

    # Sort descending by score
    leaderboard.sort(key=lambda x: x['avg_weighted_score'], reverse=True)

    # Prepare Chart.js data
    labels = [u['username'] for u in leaderboard]
    data = [u['avg_weighted_score'] for u in leaderboard]

    return render_template(
        'analytics/weighted_scores.html',
        leaderboard=leaderboard,
        chart_labels=labels,
        chart_data=data
    )

@main.route('/underperformance')
def underperformance():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return "Access denied", 403

    # Get all non-admin users
    users = User.query.filter(User.role.notin_(['admin'])).all()
    flagged_users = []

    for user in users:
        kpis = KPI.query.filter_by(employee_id=user.id).all()
        if not kpis:
            continue

        avg_score = sum(k.score for k in kpis) / len(kpis)
        if avg_score < 50:
            last_kpi_date = max(k.date for k in kpis)
            flagged_users.append({
                'username': user.username,
                'role': user.role,
                'avg_score': avg_score,
                'last_kpi_date': last_kpi_date.strftime('%Y-%m-%d')
            })

    return render_template('analytics/underperformance.html', flagged_users=flagged_users)

@main.route('/analytics/kpi-volume')
def kpi_submission_volume():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    from collections import defaultdict

    # Fetch all supervisor/HR-submitted KPIs
    kpis = KPI.query.filter(KPI.submitted_by != session.get('username')).all()

    # Group KPI submissions by month (YYYY-MM)
    submission_counts = defaultdict(int)
    for kpi in kpis:
        key = kpi.date.strftime("%Y-%m")  # You can use "%Y-%W" for weekly
        submission_counts[key] += 1

    # Sort by date
    sorted_dates = sorted(submission_counts.keys())
    counts = [submission_counts[date] for date in sorted_dates]

    return render_template('analytics/kpi_volume.html', labels=sorted_dates, data=counts)

@main.route('/analytics/submission-type-breakdown')
def submission_type_breakdown():
    from collections import defaultdict
    from datetime import datetime
    import calendar

    all_kpis = KPI.query.all()
    submission_counts = defaultdict(int)
    submission_type = {'employee': 0, 'supervisor': 0}
    monthly_trends = {'employee': defaultdict(int), 'supervisor': defaultdict(int)}

    for kpi in all_kpis:
        user = User.query.get(kpi.employee_id)
        if not user:
            continue
        submission_counts[user.username] += 1

        if kpi.submitted_by == user.username:
            submitter_type = 'employee'
        else:
            submitter_type = 'supervisor'

        submission_type[submitter_type] += 1
        if kpi.date:
            month_str = kpi.date.strftime('%Y-%m')
            monthly_trends[submitter_type][month_str] += 1

    months = sorted(set(monthly_trends['employee'].keys()) | set(monthly_trends['supervisor'].keys()))
    employee_counts = [monthly_trends['employee'].get(m, 0) for m in months]
    supervisor_counts = [monthly_trends['supervisor'].get(m, 0) for m in months]

    return render_template(
        'analytics/submission_type_breakdown.html',
        submission_counts=dict(submission_counts),
        submission_type=submission_type,
        months=months,
        employee_counts=employee_counts,
        supervisor_counts=supervisor_counts
    )

@main.route('/analytics/weighting-impact')
def weighting_impact():
    from collections import defaultdict

    all_kpis = KPI.query.all()

    user_scores = defaultdict(lambda: defaultdict(float))
    total_weights_by_category = defaultdict(float)

    for kpi in all_kpis:
        if kpi.submitted_by == session.get('username'):
            continue  # Only use supervisor-submitted KPIs

        user = User.query.get(kpi.employee_id)
        if not user:
            continue

        contribution = kpi.score * kpi.weight
        user_scores[user.username][kpi.kpi_name] += contribution
        total_weights_by_category[kpi.kpi_name] += kpi.weight

    # Structure data for Chart.js
    stacked_data = []
    users = list(user_scores.keys())
    categories = sorted({k for user_data in user_scores.values() for k in user_data.keys()})
    
    for category in categories:
        stacked_data.append({
            'label': category,
            'data': [user_scores[user].get(category, 0) for user in users],
        })

    pie_labels = list(total_weights_by_category.keys())
    pie_data = list(total_weights_by_category.values())

    return render_template(
        'analytics/weighting_impact.html',
        users=users,
        categories=categories,
        stacked_data=stacked_data,
        pie_labels=pie_labels,
        pie_data=pie_data
    )

@main.route('/analytics/overachievers')
def overachievers():
    kpis = KPI.query.all()

    a_player_counts = defaultdict(int)
    grade_distribution = Counter()
    
    # Fetch all users and their roles
    for kpi in kpis:
        grade_distribution[kpi.grade] += 1
        if kpi.grade == "Excellent - A Player":
            user = User.query.get(kpi.employee_id)
            a_player_counts[user.username] += 1
    
    # Sort the A Player counts
    user_roles = {user.username: user.role for user in User.query.all()}

    leaderboard = sorted(
        [
            {
                "username": username,
                "role": user_roles.get(username, "Unknown"),
                "a_player_count": count
            }
            for username, count in a_player_counts.items()
        ],
        key=lambda x: x["a_player_count"],
        reverse=True
    )

    # Prepare data for Chart.js
    chart_data = {
        "bar": {
            "labels": list(a_player_counts.keys()),
            "data": list(a_player_counts.values())
        },
        "pie": {
            "labels": list(grade_distribution.keys()),
            "data": list(grade_distribution.values())
        }
    }

    return render_template('analytics/overachievers.html', leaderboard=leaderboard, chart_data=chart_data)

@main.route('/analytics/timesheet-summary')
def timesheet_summary():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    from sqlalchemy.sql import func
    users = User.query.filter(User.role.notin_(['admin'])).all()

    # ----- TABLE: Per-user Summary -----
    summary = []
    for user in users:
        timesheets = Timesheet.query.filter_by(employee_id=user.id).all()

        total_seconds = sum(
            (entry.clock_out - entry.clock_in).total_seconds()
            for entry in timesheets
            if entry.clock_in and entry.clock_out
        )
        total_hours = round(total_seconds / 3600, 2)
        days_worked = len([entry for entry in timesheets if entry.clock_in and entry.clock_out])
        avg_daily_hours = round(total_hours / days_worked, 2) if days_worked else 0

        summary.append({
            "username": user.username,
            "role": user.role,
            "total_hours": total_hours,
            "days_worked": days_worked,
            "avg_daily_hours": avg_daily_hours,
        })

    # ----- CHART: Per-date Average Summary -----
    all_entries = Timesheet.query.order_by(Timesheet.clock_in.asc()).all()

    daily_summary = {}
    for entry in all_entries:
        if entry.clock_in and entry.clock_out:
            date_str = entry.clock_in.date().strftime('%Y-%m-%d')
            hours = (entry.clock_out - entry.clock_in).total_seconds() / 3600
            daily_summary.setdefault(date_str, []).append(hours)

    chart_labels = sorted(daily_summary.keys())
    avg_hours = [round(sum(hours) / len(hours), 2) for date, hours in sorted(daily_summary.items())]

    return render_template(
        'analytics/timesheet_summary.html',
        summary=summary,
        chart_labels=chart_labels,
        chart_data=avg_hours
    )
    
@main.route('/analytics/attendance-flags')  # --- Attendance Flags route view ---
def attendance_flags():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    users = User.query.filter(User.role.notin_(['admin'])).all()
    all_flags = []

    for user in users:
        timesheets = Timesheet.query.filter_by(employee_id=user.id).order_by(Timesheet.clock_in.desc()).all()
        flags = []
        for entry in timesheets:
            entry_flags = []

            if entry.clock_in and not entry.clock_out:
                entry_flags.append("⚠️ Missing Clock Out")
            if entry.clock_in and entry.clock_in.time() > datetime.strptime("09:15", "%H:%M").time():
                entry_flags.append("❗ Late Clock In")
            if entry.clock_out and entry.clock_out.time() < datetime.strptime("16:45", "%H:%M").time():
                entry_flags.append("❗ Early Clock Out")

            if entry_flags:
                all_flags.append({
                    "username": user.username,
                    "role": user.role,
                    "date": entry.clock_in.strftime('%Y-%m-%d'),
                    "clock_in": entry.clock_in.strftime('%H:%M:%S') if entry.clock_in else "N/A",
                    "clock_out": entry.clock_out.strftime('%H:%M:%S') if entry.clock_out else "N/A",
                    "flag": ", ".join(entry_flags)
                })

    return render_template('analytics/attendance_flags.html', flags=all_flags)

@main.route('/team-timesheets') # --- Team Timesheets route view ---
def team_timesheets():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # Only supervisors/HR/managers should see this
    role = session.get('role')
    if role not in ['supervisor', 'hr', 'senior manager', 'admin']:
        return redirect(url_for('main.dashboard'))

    today = date.today()

    # Fetch employees eligible for timesheet tracking (exclude admin/hr/supervisors themselves)
    employees = User.query.filter(User.role.notin_(['admin', 'hr', 'supervisor', 'senior manager'])).all()

    # Dynamically add a 'clocked_in' property for each employee
    for emp in employees:
        latest_entry = Timesheet.query.filter(
            Timesheet.employee_id == emp.id,
            Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
        ).order_by(Timesheet.id.desc()).first()

        # If they clocked in today but haven't clocked out yet
        if latest_entry and not latest_entry.clock_out:
            emp.clocked_in = True
        else:
            emp.clocked_in = False

    return render_template('timesheets/team_timesheets.html', employees=employees)

# --- Possibly problematic Route to View specific employee timesheet history ---
@main.route('/team-timesheets/<int:employee_id>')
def view_timesheet_history(employee_id):
    employee = User.query.get(employee_id)
    if not employee:
        return "Employee not found", 404

    timesheets = Timesheet.query.filter_by(employee_id=employee_id).order_by(Timesheet.clock_in.desc()).all()

    return render_template('timesheets/my_timesheet_history.html', employee=employee, timesheets=timesheets)

@main.route('/timesheet/<int:employee_id>')
def view_employee_timesheet(employee_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # Only HR, Supervisor, or Manager should be able to view other users' timesheets
    role = session.get('role', '').lower()
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    employee = User.query.get_or_404(employee_id)
    timesheets = Timesheet.query.filter_by(employee_id=employee_id).order_by(Timesheet.clock_in.desc()).all()

    return render_template('timesheets/view_employee_timesheet.html', employee=employee, timesheets=timesheets)

@main.route('/timesheet/history')
def my_timesheet_history():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    timesheets = Timesheet.query.filter_by(employee_id=user_id).order_by(Timesheet.clock_in.desc()).all()

    return render_template('timesheets/my_timesheet_history.html', timesheets=timesheets)

@main.route('/timesheets/daily')
def daily_timesheet():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    today = date.today()
    # Fetch today's timesheet entries
    entries = Timesheet.query.filter(
        Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
    ).order_by(Timesheet.clock_in.asc()).all()

    return render_template('timesheets/daily_timesheet.html', entries=entries)

@main.route('/profile')
#@login_required
def profile():
    return render_template('profile.html', user='user_id')
'''







'''earlier backup


from flask import Blueprint, render_template, redirect, url_for, request, session, jsonify
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from app.extensions import db
from app.models import User, KPI, Timesheet, KPIConfig
from collections import defaultdict, Counter
from sqlalchemy import func
from flask_login import LoginManager

main = Blueprint('main', __name__)

# Role-based KPI configurations
# Define the KPI sets for each role. This should be a dictionary where the keys are the role names and the values are dictionaries of KPIs and their weights. The weights should sum up to 1 for each role.

ROLE_KPI_SETS = {
    "employee": {
        "Punctuality": 0.3,
        "Task Completion": 0.4,
        "Teamwork": 0.3
    },
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

TIMESHEET_ROLES = ['employee', 'carpenter', 'blaster', 'graphic designer']

@main.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'  # Redirect to login page if not logged in
    login_manager.login_message = "❗ Please log in to access this page."
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            return redirect(url_for('main.dashboard'))
        return render_template('login.html', error='Invalid credentials', datetime=datetime)
    return render_template('login.html', datetime=datetime, hide_nav=True)

@main.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user = User.query.get(session['user_id'])
    session['role'] = user.role
    session['username'] = user.username

    # HR-style dashboard for hr and supervisor-type users
    if user.role in ['hr', 'supervisor', 'supervisor1']:
        return render_template('dashboard_hr.html', username=user.username, role=user.role)

    # Manager-style dashboard
    elif user.role == 'senior manager':
        return render_template('dashboard_manager.html', username=user.username, role=user.role)
    
    # Admin-style dashboard
    elif user.role == 'admin':
        return render_template('dashboard_admin.html', username=user.username, role=user.role)

    # Default employee-style dashboard
    return render_template('dashboard.html', username=user.username, role=user.role)

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main.route('/timesheet', methods=['GET', 'POST'])
def timesheet():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    if session.get('role').lower() not in TIMESHEET_ROLES:
        render_template('unauthorized_timesheet.html'), 403
    
    # Get the current user ID and today's date
    user_id = session['user_id']
    today = date.today()
    message = ""
    action = None

    entry = Timesheet.query.filter(
        Timesheet.employee_id == user_id,
        Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
    ).order_by(Timesheet.id.desc()).first()

    if request.method == 'POST':
        now = datetime.now()
        location = request.form['location']
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not entry:
            new_entry = Timesheet(
                employee_id=user_id,
                clock_in=now,
                location=location,
                latitude=latitude,
                longitude=longitude
            )
            db.session.add(new_entry)
            db.session.commit()
            message = "✅ Clocked in successfully!"
        elif not entry.clock_out:
            entry.clock_out = now
            entry.latitude = latitude
            entry.longitude = longitude
            db.session.commit()
            message = "✅ Clocked out successfully!"
        else:
            message = "✔️ You have already clocked out today."

        return redirect(url_for('main.timesheet'))

    if not entry:
        action = 'clock_in'
    elif entry and not entry.clock_out:
        action = 'clock_out'
    else:
        action = 'done'

    return render_template('timesheets/timesheet.html', action=action, message=message, entry=entry)

# Updated /kpi route with all fixes and restrictions implemented
@main.route('/kpi', methods=['GET', 'POST'])
def kpi_entry():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    user_id = session['user_id']
    username = session.get('username')
    is_supervisor = role in ['supervisor', 'hr', 'senior manager', 'admin']

    employees = []
    selected_user = None
    kpi_configs = []
    message = ""

    if is_supervisor:
        employees = User.query.filter(User.role.notin_(['admin', 'hr', 'supervisor'])).all()

        # Handle POST submission or default to first employee on GET
        if request.method == 'POST' and 'employee_id' in request.form:
            selected_user_id = int(request.form.get('employee_id'))
            selected_user = User.query.get(selected_user_id)
        elif employees:
            selected_user = employees[0]  # default selection on GET if list not empty
    else:
        selected_user = User.query.get(user_id)

    if not selected_user:
        return render_template('error.html', message="❌ No employee selected or available."), 400

    selected_role = selected_user.role.lower()
    kpi_configs = KPIConfig.query.filter_by(role=selected_role).all()

    if not kpi_configs:
        return render_template('error.html', message=f"❌ No KPI configuration found for role: {selected_role}"), 400

    # Handle KPI submission
    if request.method == 'POST' and 'kpi_name' in request.form and request.form.get('score'):
        
        try:
            score = float(request.form['score'])
        except ValueError:
            message = "⚠️ Invalid score submitted."
            return render_template(
                'kpi.html',
                message=message,
                kpi_options={cfg.kpi_name: cfg.weight for cfg in kpi_configs},
                employees=employees,
                is_supervisor=is_supervisor,
                selected_user=selected_user
            )
        kpi_name = request.form['kpi_name']
        
        # Check if the KPI has already been submitted today
        existing_kpi = KPI.query.filter_by(
            employee_id=selected_user.id,
            date=date.today(),
            kpi_name=kpi_name
        ).first()

        if existing_kpi:
            message = f"⚠️ {selected_user.username} has already submitted '{kpi_name}' KPI today."
        else:
            config = next((cfg for cfg in kpi_configs if cfg.kpi_name == kpi_name), None)
            weight = config.weight if config else 0.0
            grade = (
                "Excellent - A Player" if score >= 85 else
                "Good - B Player" if score >= 70 else
                "Average - C Player" if score >= 50 else
                "Poor - D Player"
            )

            new_kpi = KPI(
                employee_id=selected_user.id,
                kpi_name=kpi_name,
                score=score,
                weight=weight,
                grade=grade,
                date=date.today(),
                submitted_by=username
            )
            db.session.add(new_kpi)
            db.session.commit()
            message = f"✅ KPI submitted for {selected_user.username}: {kpi_name} — Grade: {grade}"

    return render_template(
        'kpi.html',
        message=message,
        kpi_options={cfg.kpi_name: cfg.weight for cfg in kpi_configs},
        employees=employees,
        is_supervisor=is_supervisor,
        selected_user=selected_user
    )

@main.route('/kpi/history')
def kpi_history():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    username = session['username']

    # Get all KPI entries for the current user
    all_kpis = KPI.query.filter_by(employee_id=user_id).order_by(KPI.date.desc()).all()

    # Split them into supervisor- and self-submitted
    supervisor_kpis = [k for k in all_kpis if k.submitted_by != username]
    self_kpis = [k for k in all_kpis if k.submitted_by == username]

    # Show all for the table
    kpis = all_kpis

    # Use supervisor KPIs for charts if available, else fallback to self-submitted
    kpi_source = supervisor_kpis if supervisor_kpis else self_kpis

    # Prepare data for charts
    kpi_data = [
        {
            "date": k.date.strftime("%Y-%m-%d"),
            "kpi_name": k.kpi_name,
            "score": k.score,
            "weight": k.weight,
            "grade": k.grade,
            "submitted_by": k.submitted_by
        }
        for k in kpi_source
    ]

    return render_template('kpi_history.html', kpis=kpis, kpi_data=kpi_data, current_user=username)

@main.route('/view-reports')
def view_reports():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    kpis = KPI.query.order_by(KPI.date.desc()).all()

    # Convert to dict for chart use
    kpi_data = [
        {
            "date": kpi.date.strftime('%Y-%m-%d'),
            "employee_id": kpi.employee_id,
            "kpi_name": kpi.kpi_name,
            "score": kpi.score,
            "weight": kpi.weight,
            "grade": kpi.grade,
            "submitted_by": kpi.submitted_by
        }
        for kpi in kpis
    ]

    return render_template("view_reports.html", kpis=kpis, kpi_data=kpi_data)

@main.route('/manage_employees')
def manage_employees():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role', '').lower()

    # ✅ Include senior manager
    if role not in ['admin', 'hr', 'supervisor', 'manager', 'senior manager']:
        return render_template('error.html', message="❌ You are not authorized to access this page."), 403

    employees = User.query.filter(User.role.notin_([
        'admin', 'hr', 'supervisor', 'manager', 'senior manager'
    ])).all()

    return render_template('manage_employees.html', employees=employees)

@main.route('/analytics/kpi-trends')
def kpi_trends():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    username = session.get('username')
    user_id = session.get('user_id')

    all_kpis = KPI.query.filter_by(employee_id=user_id).order_by(KPI.date.asc()).all()
    supervisor_kpis = [k for k in all_kpis if k.submitted_by != username]
    self_kpis = [k for k in all_kpis if k.submitted_by == username]

    def format_kpis(kpi_list):
        return [
            {
                "date": k.date.strftime('%Y-%m-%d'),
                "score": k.score,
                "kpi_name": k.kpi_name
            } for k in kpi_list
        ]

    return render_template(
        'analytics/kpi_trends.html',
        chart_data=format_kpis(supervisor_kpis),
        fallback_data=format_kpis(self_kpis),
        has_supervisor_data=len(supervisor_kpis) > 0,
        has_self_data=len(self_kpis) > 0
    )

@main.route('/analytics/team-comparisons')
def team_comparisons():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    from sqlalchemy.sql import func
    # Get all KPIs submitted by supervisors/HR
    supervisor_kpis = KPI.query.filter(KPI.submitted_by != session.get('username')).all()

    # Aggregate KPI scores by role and category
    role_kpi_data = {}
    for kpi in supervisor_kpis:
        user = User.query.get(kpi.employee_id)
        if not user:
            continue
        role = user.role.title()
        role_kpi_data.setdefault(role, {})
        role_kpi_data[role].setdefault(kpi.kpi_name, []).append(kpi.score)

    # Prepare data for charts
    avg_role_scores = {}  # overall per role
    category_scores = {}  # per category per role

    for role, kpis in role_kpi_data.items():
        all_scores = []
        for kpi_name, scores in kpis.items():
            avg_score = sum(scores) / len(scores)
            all_scores.extend(scores)
            category_scores.setdefault(kpi_name, {})[role] = avg_score
        avg_role_scores[role] = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0

    return render_template(
        'team_comparisons.html',
        avg_role_scores=avg_role_scores,
        category_scores=category_scores
    )

@main.route('/analytics/category-breakdown')
def category_breakdown():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role', '').lower()
    user_id = session['user_id']

    if role in ['admin', 'hr', 'supervisor', 'senior manager']:
        # View for all employees
        kpis = KPI.query.all()
    else:
        # Restrict to current user
        kpis = KPI.query.filter_by(employee_id=user_id).all()

    category_totals = {}
    category_counts = {}

    for k in kpis:
        category_totals[k.kpi_name] = category_totals.get(k.kpi_name, 0) + k.score
        category_counts[k.kpi_name] = category_counts.get(k.kpi_name, 0) + 1

    avg_scores = {
        name: round(category_totals[name] / category_counts[name], 2)
        for name in category_totals
    }

    return render_template('analytics/category_breakdown.html', avg_scores=avg_scores)

@main.route('/analytics/weighted-scores')
def weighted_scores():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    # Fetch only supervisor-submitted KPIs for analytics integrity
    username = session.get('username')
    supervisor_kpis = KPI.query.filter(KPI.submitted_by != username).all()

    # Group weighted scores by employee
    scores_by_user = {}
    counts_by_user = {}
    for k in supervisor_kpis:
        uid = k.employee_id
        weighted = k.score * k.weight
        scores_by_user.setdefault(uid, 0)
        counts_by_user.setdefault(uid, 0)
        scores_by_user[uid] += weighted
        counts_by_user[uid] += 1

    # Compute average weighted score per user
    leaderboard = []
    for uid, total_wscore in scores_by_user.items():
        count = counts_by_user[uid]
        avg_w = round(total_wscore / count, 2) if count else 0
        user = User.query.get(uid)
        leaderboard.append({
            'username': user.username if user else f'User {uid}',
            'avg_weighted_score': avg_w
        })

    # Sort descending by score
    leaderboard.sort(key=lambda x: x['avg_weighted_score'], reverse=True)

    # Prepare Chart.js data
    labels = [u['username'] for u in leaderboard]
    data = [u['avg_weighted_score'] for u in leaderboard]

    return render_template(
        'analytics/weighted_scores.html',
        leaderboard=leaderboard,
        chart_labels=labels,
        chart_data=data
    )

@main.route('/underperformance')
def underperformance():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return "Access denied", 403

    # Get all non-admin users
    users = User.query.filter(User.role.notin_(['admin'])).all()
    flagged_users = []

    for user in users:
        kpis = KPI.query.filter_by(employee_id=user.id).all()
        if not kpis:
            continue

        avg_score = sum(k.score for k in kpis) / len(kpis)
        if avg_score < 50:
            last_kpi_date = max(k.date for k in kpis)
            flagged_users.append({
                'username': user.username,
                'role': user.role,
                'avg_score': avg_score,
                'last_kpi_date': last_kpi_date.strftime('%Y-%m-%d')
            })

    return render_template('analytics/underperformance.html', flagged_users=flagged_users)

@main.route('/analytics/kpi-volume')
def kpi_submission_volume():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    from collections import defaultdict

    # Fetch all supervisor/HR-submitted KPIs
    kpis = KPI.query.filter(KPI.submitted_by != session.get('username')).all()

    # Group KPI submissions by month (YYYY-MM)
    submission_counts = defaultdict(int)
    for kpi in kpis:
        key = kpi.date.strftime("%Y-%m")  # You can use "%Y-%W" for weekly
        submission_counts[key] += 1

    # Sort by date
    sorted_dates = sorted(submission_counts.keys())
    counts = [submission_counts[date] for date in sorted_dates]

    return render_template('analytics/kpi_volume.html', labels=sorted_dates, data=counts)

@main.route('/analytics/submission-type-breakdown')
def submission_type_breakdown():
    from collections import defaultdict
    from datetime import datetime
    import calendar

    all_kpis = KPI.query.all()
    submission_counts = defaultdict(int)
    submission_type = {'employee': 0, 'supervisor': 0}
    monthly_trends = {'employee': defaultdict(int), 'supervisor': defaultdict(int)}

    for kpi in all_kpis:
        user = User.query.get(kpi.employee_id)
        if not user:
            continue
        submission_counts[user.username] += 1

        if kpi.submitted_by == user.username:
            submitter_type = 'employee'
        else:
            submitter_type = 'supervisor'

        submission_type[submitter_type] += 1
        if kpi.date:
            month_str = kpi.date.strftime('%Y-%m')
            monthly_trends[submitter_type][month_str] += 1

    months = sorted(set(monthly_trends['employee'].keys()) | set(monthly_trends['supervisor'].keys()))
    employee_counts = [monthly_trends['employee'].get(m, 0) for m in months]
    supervisor_counts = [monthly_trends['supervisor'].get(m, 0) for m in months]

    return render_template(
        'analytics/submission_type_breakdown.html',
        submission_counts=dict(submission_counts),
        submission_type=submission_type,
        months=months,
        employee_counts=employee_counts,
        supervisor_counts=supervisor_counts
    )

@main.route('/analytics/weighting-impact')
def weighting_impact():
    from collections import defaultdict

    all_kpis = KPI.query.all()

    user_scores = defaultdict(lambda: defaultdict(float))
    total_weights_by_category = defaultdict(float)

    for kpi in all_kpis:
        if kpi.submitted_by == session.get('username'):
            continue  # Only use supervisor-submitted KPIs

        user = User.query.get(kpi.employee_id)
        if not user:
            continue

        contribution = kpi.score * kpi.weight
        user_scores[user.username][kpi.kpi_name] += contribution
        total_weights_by_category[kpi.kpi_name] += kpi.weight

    # Structure data for Chart.js
    stacked_data = []
    users = list(user_scores.keys())
    categories = sorted({k for user_data in user_scores.values() for k in user_data.keys()})
    
    for category in categories:
        stacked_data.append({
            'label': category,
            'data': [user_scores[user].get(category, 0) for user in users],
        })

    pie_labels = list(total_weights_by_category.keys())
    pie_data = list(total_weights_by_category.values())

    return render_template(
        'analytics/weighting_impact.html',
        users=users,
        categories=categories,
        stacked_data=stacked_data,
        pie_labels=pie_labels,
        pie_data=pie_data
    )

@main.route('/analytics/overachievers')
def overachievers():
    kpis = KPI.query.all()

    a_player_counts = defaultdict(int)
    grade_distribution = Counter()
    
    # Fetch all users and their roles
    for kpi in kpis:
        grade_distribution[kpi.grade] += 1
        if kpi.grade == "Excellent - A Player":
            user = User.query.get(kpi.employee_id)
            a_player_counts[user.username] += 1
    
    # Sort the A Player counts
    user_roles = {user.username: user.role for user in User.query.all()}

    leaderboard = sorted(
        [
            {
                "username": username,
                "role": user_roles.get(username, "Unknown"),
                "a_player_count": count
            }
            for username, count in a_player_counts.items()
        ],
        key=lambda x: x["a_player_count"],
        reverse=True
    )

    # Prepare data for Chart.js
    chart_data = {
        "bar": {
            "labels": list(a_player_counts.keys()),
            "data": list(a_player_counts.values())
        },
        "pie": {
            "labels": list(grade_distribution.keys()),
            "data": list(grade_distribution.values())
        }
    }

    return render_template('analytics/overachievers.html', leaderboard=leaderboard, chart_data=chart_data)

@main.route('/analytics/timesheet-summary')
def timesheet_summary():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    from sqlalchemy.sql import func
    users = User.query.filter(User.role.notin_(['admin'])).all()

    # ----- TABLE: Per-user Summary -----
    summary = []
    for user in users:
        timesheets = Timesheet.query.filter_by(employee_id=user.id).all()

        total_seconds = sum(
            (entry.clock_out - entry.clock_in).total_seconds()
            for entry in timesheets
            if entry.clock_in and entry.clock_out
        )
        total_hours = round(total_seconds / 3600, 2)
        days_worked = len([entry for entry in timesheets if entry.clock_in and entry.clock_out])
        avg_daily_hours = round(total_hours / days_worked, 2) if days_worked else 0

        summary.append({
            "username": user.username,
            "role": user.role,
            "total_hours": total_hours,
            "days_worked": days_worked,
            "avg_daily_hours": avg_daily_hours,
        })

    # ----- CHART: Per-date Average Summary -----
    all_entries = Timesheet.query.order_by(Timesheet.clock_in.asc()).all()

    daily_summary = {}
    for entry in all_entries:
        if entry.clock_in and entry.clock_out:
            date_str = entry.clock_in.date().strftime('%Y-%m-%d')
            hours = (entry.clock_out - entry.clock_in).total_seconds() / 3600
            daily_summary.setdefault(date_str, []).append(hours)

    chart_labels = sorted(daily_summary.keys())
    avg_hours = [round(sum(hours) / len(hours), 2) for date, hours in sorted(daily_summary.items())]

    return render_template(
        'analytics/timesheet_summary.html',
        summary=summary,
        chart_labels=chart_labels,
        chart_data=avg_hours
    )
    
@main.route('/analytics/attendance-flags')  # --- Attendance Flags route view ---
def attendance_flags():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    role = session.get('role')
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    users = User.query.filter(User.role.notin_(['admin'])).all()
    all_flags = []

    for user in users:
        timesheets = Timesheet.query.filter_by(employee_id=user.id).order_by(Timesheet.clock_in.desc()).all()
        flags = []
        for entry in timesheets:
            entry_flags = []

            if entry.clock_in and not entry.clock_out:
                entry_flags.append("⚠️ Missing Clock Out")
            if entry.clock_in and entry.clock_in.time() > datetime.strptime("09:15", "%H:%M").time():
                entry_flags.append("❗ Late Clock In")
            if entry.clock_out and entry.clock_out.time() < datetime.strptime("16:45", "%H:%M").time():
                entry_flags.append("❗ Early Clock Out")

            if entry_flags:
                all_flags.append({
                    "username": user.username,
                    "role": user.role,
                    "date": entry.clock_in.strftime('%Y-%m-%d'),
                    "clock_in": entry.clock_in.strftime('%H:%M:%S') if entry.clock_in else "N/A",
                    "clock_out": entry.clock_out.strftime('%H:%M:%S') if entry.clock_out else "N/A",
                    "flag": ", ".join(entry_flags)
                })

    return render_template('analytics/attendance_flags.html', flags=all_flags)

@main.route('/team-timesheets') # --- Team Timesheets route view ---
def team_timesheets():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    # Only supervisors/HR/managers should see this
    role = session.get('role')
    if role not in ['supervisor', 'hr', 'senior manager', 'admin']:
        return redirect(url_for('main.dashboard'))

    today = date.today()

    # Fetch employees eligible for timesheet tracking (exclude admin/hr/supervisors themselves)
    employees = User.query.filter(User.role.notin_(['admin', 'hr', 'supervisor', 'senior manager'])).all()

    # Dynamically add a 'clocked_in' property for each employee
    for emp in employees:
        latest_entry = Timesheet.query.filter(
            Timesheet.employee_id == emp.id,
            Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
        ).order_by(Timesheet.id.desc()).first()

        # If they clocked in today but haven't clocked out yet
        if latest_entry and not latest_entry.clock_out:
            emp.clocked_in = True
        else:
            emp.clocked_in = False

    return render_template('timesheets/team_timesheets.html', employees=employees)

# --- Possibly problematic Route to View specific employee timesheet history ---
@main.route('/team-timesheets/<int:employee_id>')
def view_timesheet_history(employee_id):
    employee = User.query.get(employee_id)
    if not employee:
        return "Employee not found", 404

    timesheets = Timesheet.query.filter_by(employee_id=employee_id).order_by(Timesheet.clock_in.desc()).all()

    return render_template('timesheets/my_timesheet_history.html', employee=employee, timesheets=timesheets)

@main.route('/timesheet/<int:employee_id>')
def view_employee_timesheet(employee_id):
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # Only HR, Supervisor, or Manager should be able to view other users' timesheets
    role = session.get('role', '').lower()
    if role not in ['hr', 'supervisor', 'senior manager', 'admin']:
        return render_template('error.html', message=f"❗Access Denied. You are not authorized to view this page."), 403

    employee = User.query.get_or_404(employee_id)
    timesheets = Timesheet.query.filter_by(employee_id=employee_id).order_by(Timesheet.clock_in.desc()).all()

    return render_template('timesheets/view_employee_timesheet.html', employee=employee, timesheets=timesheets)

@main.route('/timesheet/history')
def my_timesheet_history():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    timesheets = Timesheet.query.filter_by(employee_id=user_id).order_by(Timesheet.clock_in.desc()).all()

    return render_template('timesheets/my_timesheet_history.html', timesheets=timesheets)

@main.route('/timesheets/daily')
def daily_timesheet():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    today = date.today()
    # Fetch today's timesheet entries
    entries = Timesheet.query.filter(
        Timesheet.clock_in >= datetime.combine(today, datetime.min.time())
    ).order_by(Timesheet.clock_in.asc()).all()

    return render_template('timesheets/daily_timesheet.html', entries=entries)

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user='user_id')

'''