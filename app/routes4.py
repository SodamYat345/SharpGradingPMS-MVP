from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, login_manager
from app.models import User, KPI, KPIConfig, Timesheet
from werkzeug.security import check_password_hash
from datetime import datetime
from sqlalchemy import func

main = Blueprint("main", __name__)

# ---- LOGIN & LOGOUT ----
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid credentials", "error")
    return render_template("login.html")

@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# ---- DASHBOARD ----
@main.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# ---- KPI ROUTES ----
@main.route("/submit-kpi", endpoint="kpi_entry", methods=["GET", "POST"])
@login_required
def submit_kpi():
    config = KPIConfig.query.filter_by(role=current_user.role).all()
    if request.method == "POST":
        for item in config:
            score = float(request.form.get(item.kpi_name, 0))
            weight = item.weight
            grade = calculate_grade(score)
            entry = KPI(
                employee_id=current_user.id,
                kpi_name=item.kpi_name,
                score=score,
                weight=weight,
                grade=grade,
                date=datetime.utcnow().date(),
                submitted_by=current_user.username
            )
            db.session.add(entry)
        db.session.commit()
        flash("KPI submitted successfully")
        return redirect(url_for("main.dashboard"))
    return render_template("submit_kpi.html", config=config)

@main.route("/view-kpis", endpoint="kpi_history", methods=["GET"])
@login_required
def view_kpis():
    kpis = KPI.query.filter_by(employee_id=current_user.id).order_by(KPI.date.desc()).all()
    return render_template("kpi_history.html", kpis=kpis)


# ---- TIMESHEET ROUTES ----
@main.route("/clock-in-out", endpoint="timesheet", methods=["GET", "POST"])
@login_required
def clock_in_out():
    if request.method == "POST":
        action = request.form["action"]
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")
        location = request.form.get("location")

        if action == "clock-in":
            entry = Timesheet(
                employee_id=current_user.id,
                clock_in=datetime.utcnow(),
                latitude=latitude,
                longitude=longitude,
                location=location
            )
            db.session.add(entry)
        elif action == "clock-out":
            entry = Timesheet.query.filter_by(employee_id=current_user.id).order_by(Timesheet.id.desc()).first()
            if entry and entry.clock_out is None:
                entry.clock_out = datetime.utcnow()
        db.session.commit()
        flash(f"{action.replace('-', ' ').capitalize()} recorded.")
        return redirect(url_for("main.clock_in_out"))

    timesheets = Timesheet.query.filter_by(employee_id=current_user.id).order_by(Timesheet.clock_in.desc()).all()
    return render_template("clock_in_out.html", timesheets=timesheets)


# ---- ANALYTICS EXAMPLES ----
@main.route("/analytics/weighted-scores")
@login_required
def weighted_scores():
    if current_user.role not in ["admin", "supervisor", "hr"]:
        return redirect(url_for("main.dashboard"))

    data = (
        db.session.query(
            KPI.employee_id,
            func.sum(KPI.score * KPI.weight).label("total_score"),
            func.sum(KPI.weight).label("total_weight")
        )
        .group_by(KPI.employee_id)
        .all()
    )

    results = []
    for emp_id, total_score, total_weight in data:
        user = User.query.get(emp_id)
        weighted_score = round(total_score / total_weight, 2) if total_weight else 0
        results.append({
            "user": user.username if user else f"User {emp_id}",
            "weighted_score": weighted_score
        })

    return render_template("analytics/weighted_scores.html", results=results)


# ---- UTILITY ----
def calculate_grade(score):
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    return "F"


# ---- ERROR HANDLING ----
@main.app_errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@main.app_errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500
# ---- REGISTER BLUEPRINT ----
def register_routes(app):
    app.register_blueprint(main)
    app.add_url_rule("/", endpoint="login")
    app.add_url_rule("/logout", endpoint="logout")
    app.add_url_rule("/dashboard", endpoint="dashboard")
    app.add_url_rule("/submit-kpi", endpoint="submit_kpi")
    app.add_url_rule("/view-kpis", endpoint="kpi_history")
    app.add_url_rule("/clock-in-out", endpoint="timesheet")
    app.add_url_rule("/analytics/weighted-scores", endpoint="weighted_scores")
    app.add_url_rule("/404", endpoint="page_not_found")
    app.add_url_rule("/500", endpoint="internal_server_error")
# Register the routes with the Flask app
# from app import create_app
# app = create_app()
# register_routes(app)