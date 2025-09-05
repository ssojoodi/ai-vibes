# app.py
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    send_file,
)
from functools import wraps
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    create_access_token,
    get_jwt_identity,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import csv
import io
from enum import Enum

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///timesheet.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "jwt-secret-string")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
CORS(app)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "web_login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            flash("You must be an admin to access this page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)

    return decorated_function


# Web Routes
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("web_login"))


@app.route("/login", methods=["GET", "POST"])
def web_login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username, is_active=True).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("web_login"))


@app.route("/users")
@login_required
@admin_required
def user_list():
    users = User.query.order_by(User.username).all()
    return render_template("auth/user_list.html", users=users)


@app.route("/users/bulk-upload", methods=["GET", "POST"])
@login_required
@admin_required
def bulk_upload_users():
    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file uploaded", "danger")
            return redirect(url_for("bulk_upload_users"))

        csv_file = request.files["csv_file"]
        if csv_file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("bulk_upload_users"))

        if not csv_file.filename.endswith(".csv"):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("bulk_upload_users"))

        try:
            # Read CSV file
            stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)

            success_count = 0
            error_messages = []

            for row in csv_reader:
                # Validate required fields
                required_fields = ["email", "first_name", "last_name", "role"]
                missing_fields = [
                    field for field in required_fields if not row.get(field)
                ]

                if missing_fields:
                    error_messages.append(
                        f"Missing required fields {', '.join(missing_fields)} for {row.get('email', 'unknown email')}"
                    )
                    continue

                # Check if user already exists
                if User.query.filter_by(email=row["email"]).first():
                    error_messages.append(
                        f"User with email {row['email']} already exists"
                    )
                    continue

                try:
                    # Generate username from email
                    username = row["email"].split("@")[0]
                    base_username = username
                    counter = 1
                    while User.query.filter_by(username=username).first():
                        username = f"{base_username}{counter}"
                        counter += 1

                    # Generate random password
                    password = os.urandom(8).hex()

                    # Create user
                    user = User(
                        username=username,
                        email=row["email"],
                        password_hash=generate_password_hash(password),
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        role=UserRole(row["role"]),
                    )
                    db.session.add(user)
                    success_count += 1

                    # TODO: Send welcome email with credentials if send_emails is checked

                except Exception as e:
                    error_messages.append(
                        f"Error creating user {row.get('email')}: {str(e)}"
                    )
                    continue

            db.session.commit()

            # Show results
            if success_count > 0:
                flash(f"Successfully created {success_count} users", "success")
            if error_messages:
                for msg in error_messages:
                    flash(msg, "danger")

            return redirect(url_for("user_list"))

        except Exception as e:
            flash(f"Error processing CSV file: {str(e)}", "danger")
            return redirect(url_for("bulk_upload_users"))

    return render_template("auth/bulk_upload.html")


@app.route("/users/download-template")
@login_required
@admin_required
def download_template():
    return send_file(
        "static/templates/user_upload_template.csv",
        mimetype="text/csv",
        as_attachment=True,
        download_name="user_upload_template.csv",
    )


@app.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def web_signup():
    if request.method == "POST":
        # Validate required fields
        required_fields = [
            "username",
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "role",
        ]
        for field in required_fields:
            if not request.form.get(field):
                flash(f"{field.replace('_', ' ').title()} is required", "danger")
                return redirect(url_for("web_signup"))

        # Check if passwords match
        if request.form["password"] != request.form["confirm_password"]:
            flash("Passwords do not match", "danger")
            return redirect(url_for("web_signup"))

        # Check if user already exists
        if User.query.filter_by(username=request.form["username"]).first():
            flash("Username already exists", "danger")
            return redirect(url_for("web_signup"))

        if User.query.filter_by(email=request.form["email"]).first():
            flash("Email already exists", "danger")
            return redirect(url_for("web_signup"))

        # Create new user
        user = User(
            username=request.form["username"],
            email=request.form["email"],
            password_hash=generate_password_hash(request.form["password"]),
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            role=UserRole(request.form["role"]),
        )

        db.session.add(user)
        db.session.commit()

        flash("User created successfully", "success")
        return redirect(url_for("user_list"))

    return render_template("auth/signup.html", roles=UserRole)


@app.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)

    # Prevent self-deactivation
    if user.id == current_user.id:
        flash("You cannot deactivate your own account", "danger")
        return redirect(url_for("user_list"))

    user.is_active = not user.is_active
    db.session.commit()

    status = "activated" if user.is_active else "deactivated"
    flash(f"User {user.username} has been {status}", "success")
    return redirect(url_for("user_list"))


# Admin Routes
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return redirect(url_for("user_list"))


@app.route("/admin/projects")
@login_required
@admin_required
def admin_projects():
    projects = Project.query.order_by(Project.name).all()
    return render_template(
        "admin/projects.html", projects=projects, active_page="projects"
    )


@app.route("/admin/projects/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_project():
    if request.method == "POST":
        project = Project(
            name=request.form["name"],
            code=request.form["code"],
            description=request.form.get("description", ""),
            start_date=datetime.strptime(request.form["start_date"], "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            if request.form.get("end_date")
            else None,
            budget_hours=float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0,
            is_active=True,
        )
        db.session.add(project)
        db.session.commit()
        flash("Project created successfully", "success")
        return redirect(url_for("admin_projects"))

    return render_template("admin/project_form.html", active_page="projects")


@app.route("/admin/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == "POST":
        project.name = request.form["name"]
        project.code = request.form["code"]
        project.description = request.form.get("description", "")
        project.start_date = datetime.strptime(
            request.form["start_date"], "%Y-%m-%d"
        ).date()
        project.end_date = (
            datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            if request.form.get("end_date")
            else None
        )
        project.budget_hours = (
            float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0
        )
        project.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Project updated successfully", "success")
        return redirect(url_for("admin_projects"))

    return render_template(
        "admin/project_form.html", project=project, active_page="projects"
    )


@app.route("/admin/crews")
@login_required
@admin_required
def admin_crews():
    crews = Crew.query.order_by(Crew.name).all()
    return render_template("admin/crews.html", crews=crews, active_page="crews")


@app.route("/admin/crews/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_crew():
    if request.method == "POST":
        crew = Crew(
            name=request.form["name"],
            project_id=request.form["project_id"],
            supervisor_id=request.form["supervisor_id"],
            is_active=True,
        )
        db.session.add(crew)
        db.session.commit()

        # Add crew members
        member_ids = request.form.getlist("member_ids[]")
        for user_id in member_ids:
            member = CrewMember(crew_id=crew.id, user_id=int(user_id), is_active=True)
            db.session.add(member)

        db.session.commit()
        flash("Crew created successfully", "success")
        return redirect(url_for("admin_crews"))

    projects = Project.query.filter_by(is_active=True).all()
    supervisors = User.query.filter(
        User.role.in_([UserRole.CREW_ADMIN, UserRole.SUPERINTENDENT]),
        User.is_active == True,
    ).all()
    workers = User.query.filter_by(role=UserRole.WORKER, is_active=True).all()

    return render_template(
        "admin/crew_form.html",
        projects=projects,
        supervisors=supervisors,
        workers=workers,
        active_page="crews",
    )


@app.route("/admin/crews/<int:crew_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_crew(crew_id):
    crew = Crew.query.get_or_404(crew_id)
    if request.method == "POST":
        crew.name = request.form["name"]
        crew.project_id = request.form["project_id"]
        crew.supervisor_id = request.form["supervisor_id"]
        crew.is_active = bool(request.form.get("is_active"))

        # Update crew members
        CrewMember.query.filter_by(crew_id=crew.id).delete()
        member_ids = request.form.getlist("member_ids[]")
        for user_id in member_ids:
            member = CrewMember(crew_id=crew.id, user_id=int(user_id), is_active=True)
            db.session.add(member)

        db.session.commit()
        flash("Crew updated successfully", "success")
        return redirect(url_for("admin_crews"))

    projects = Project.query.filter_by(is_active=True).all()
    supervisors = User.query.filter(
        User.role.in_([UserRole.CREW_ADMIN, UserRole.SUPERINTENDENT]),
        User.is_active == True,
    ).all()
    workers = User.query.filter_by(role=UserRole.WORKER, is_active=True).all()
    current_members = [member.user_id for member in crew.members if member.is_active]

    return render_template(
        "admin/crew_form.html",
        crew=crew,
        projects=projects,
        supervisors=supervisors,
        workers=workers,
        current_members=current_members,
        active_page="crews",
    )


@app.route("/admin/cost-codes")
@login_required
@admin_required
def admin_cost_codes():
    cost_codes = CostCode.query.order_by(CostCode.project_id, CostCode.code).all()
    return render_template(
        "admin/cost_codes.html", cost_codes=cost_codes, active_page="cost_codes"
    )


@app.route("/admin/cost-codes/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_cost_code():
    if request.method == "POST":
        cost_code = CostCode(
            code=request.form["code"],
            description=request.form["description"],
            phase=request.form["phase"],
            activity=request.form["activity"],
            project_id=request.form["project_id"],
            budget_hours=float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0,
            is_active=True,
        )
        db.session.add(cost_code)
        db.session.commit()
        flash("Cost code created successfully", "success")
        return redirect(url_for("admin_cost_codes"))

    projects = Project.query.filter_by(is_active=True).all()
    return render_template(
        "admin/cost_code_form.html", projects=projects, active_page="cost_codes"
    )


@app.route("/admin/cost-codes/<int:cost_code_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_cost_code(cost_code_id):
    cost_code = CostCode.query.get_or_404(cost_code_id)
    if request.method == "POST":
        cost_code.code = request.form["code"]
        cost_code.description = request.form["description"]
        cost_code.phase = request.form["phase"]
        cost_code.activity = request.form["activity"]
        cost_code.project_id = request.form["project_id"]
        cost_code.budget_hours = (
            float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0
        )
        cost_code.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Cost code updated successfully", "success")
        return redirect(url_for("admin_cost_codes"))

    projects = Project.query.filter_by(is_active=True).all()
    return render_template(
        "admin/cost_code_form.html",
        cost_code=cost_code,
        projects=projects,
        active_page="cost_codes",
    )


@app.route("/dashboard")
@login_required
def dashboard():
    project_id = request.args.get("project_id", type=int)
    date_from = request.args.get(
        "date_from",
        default=(datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
    )
    date_to = request.args.get(
        "date_to", default=datetime.utcnow().strftime("%Y-%m-%d")
    )

    # Get projects for filter
    projects = Project.query.filter_by(is_active=True).all()

    # Get labor summary
    labor_summary = get_labor_summary(project_id, date_from, date_to)

    # Prepare chart data
    cost_code_labels = [item["cost_code"] for item in labor_summary]
    regular_hours = [
        item["actual_hours"] - item["overtime_hours"] for item in labor_summary
    ]
    overtime_hours = [item["overtime_hours"] for item in labor_summary]
    budget_hours = [item["budget_hours"] for item in labor_summary]
    actual_hours = [item["actual_hours"] for item in labor_summary]

    return render_template(
        "dashboard/index.html",
        projects=projects,
        selected_project_id=project_id,
        date_from=date_from,
        date_to=date_to,
        labor_summary=labor_summary,
        cost_code_labels=cost_code_labels,
        regular_hours=regular_hours,
        overtime_hours=overtime_hours,
        budget_hours=budget_hours,
        actual_hours=actual_hours,
    )


@app.route("/timesheets/bulk-upload", methods=["GET", "POST"])
@login_required
def bulk_upload_timesheets():
    if request.method == "POST":
        if "csv_file" not in request.files:
            flash("No file uploaded", "danger")
            return redirect(url_for("bulk_upload_timesheets"))

        csv_file = request.files["csv_file"]
        if csv_file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("bulk_upload_timesheets"))

        if not csv_file.filename.endswith(".csv"):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("bulk_upload_timesheets"))

        try:
            # Read CSV file
            stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)

            success_count = 0
            error_messages = []
            timesheets = {}  # Dictionary to store timesheets by date and crew

            for row in csv_reader:
                try:
                    # Validate required fields
                    required_fields = [
                        "date",
                        "project_id",
                        "crew_id",
                        "user_id",
                        "cost_code_id",
                        "hours",
                    ]
                    missing_fields = [
                        field for field in required_fields if not row.get(field)
                    ]

                    if missing_fields:
                        error_messages.append(
                            f"Missing required fields {', '.join(missing_fields)} for row {success_count + 1}"
                        )
                        continue

                    # Parse and validate date
                    try:
                        entry_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                    except ValueError:
                        error_messages.append(
                            f"Invalid date format in row {success_count + 1}. Use YYYY-MM-DD format."
                        )
                        continue

                    # Get or create timesheet
                    timesheet_key = (
                        entry_date,
                        int(row["crew_id"]),
                        int(row["project_id"]),
                    )
                    if timesheet_key not in timesheets:
                        # Check if timesheet already exists
                        existing = Timesheet.query.filter_by(
                            date=entry_date,
                            crew_id=row["crew_id"],
                            project_id=row["project_id"],
                        ).first()

                        if existing and existing.status != TimesheetStatus.DRAFT:
                            error_messages.append(
                                f"Timesheet already exists and is not in draft status for date {row['date']}, "
                                f"crew {row['crew_id']}"
                            )
                            continue

                        timesheet = existing or Timesheet(
                            date=entry_date,
                            crew_id=row["crew_id"],
                            project_id=row["project_id"],
                            submitted_by=current_user.id,
                        )
                        if not existing:
                            db.session.add(timesheet)
                        timesheets[timesheet_key] = timesheet

                    # Create timesheet entry
                    entry = TimesheetEntry(
                        timesheet=timesheets[timesheet_key],
                        user_id=int(row["user_id"]),
                        cost_code_id=int(row["cost_code_id"]),
                        hours=float(row["hours"]),
                        overtime_hours=float(row.get("overtime_hours", 0)),
                        description=row.get("description", ""),
                    )
                    db.session.add(entry)
                    success_count += 1

                except Exception as e:
                    error_messages.append(
                        f"Error processing row {success_count + 1}: {str(e)}"
                    )
                    continue

            # Submit timesheets if requested
            if request.form.get("submit_timesheets"):
                for timesheet in timesheets.values():
                    timesheet.status = TimesheetStatus.PENDING_SUPER
                    timesheet.submitted_at = datetime.utcnow()

            db.session.commit()

            # Show results
            if success_count > 0:
                flash(
                    f"Successfully created {success_count} timesheet entries", "success"
                )
            if error_messages:
                for msg in error_messages:
                    flash(msg, "danger")

            return redirect(url_for("timesheet_list"))

        except Exception as e:
            flash(f"Error processing CSV file: {str(e)}", "danger")
            return redirect(url_for("bulk_upload_timesheets"))

    # Get reference data for the template
    projects = Project.query.filter_by(is_active=True).all()
    crews = Crew.query.filter_by(is_active=True).all()
    users = User.query.filter_by(is_active=True).all()
    cost_codes = CostCode.query.filter_by(is_active=True).all()

    return render_template(
        "timesheets/bulk_upload.html",
        projects=projects,
        crews=crews,
        users=users,
        cost_codes=cost_codes,
    )


@app.route("/timesheets/download-template")
@login_required
def download_timesheet_template():
    return send_file(
        "static/templates/timesheet_entry_template.csv",
        mimetype="text/csv",
        as_attachment=True,
        download_name="timesheet_entry_template.csv",
    )


@app.route("/timesheets")
@login_required
def timesheet_list():
    project_id = request.args.get("project_id", type=int)
    date = request.args.get("date")
    status = request.args.get("status")

    # Get projects for filter
    projects = Project.query.filter_by(is_active=True).all()

    # Build query
    query = Timesheet.query

    if current_user.role == UserRole.WORKER:
        crew_ids = [cm.crew_id for cm in current_user.crew_memberships if cm.is_active]
        query = query.filter(Timesheet.crew_id.in_(crew_ids))

    if project_id:
        query = query.filter(Timesheet.project_id == project_id)
    if date:
        query = query.filter(
            Timesheet.date == datetime.strptime(date, "%Y-%m-%d").date()
        )
    if status:
        query = query.filter(Timesheet.status == TimesheetStatus(status))

    timesheets = query.order_by(Timesheet.date.desc()).all()

    status_colors = {
        TimesheetStatus.DRAFT: "secondary",
        TimesheetStatus.PENDING_SUPER: "info",
        TimesheetStatus.PENDING_PM: "primary",
        TimesheetStatus.PENDING_PAYROLL: "warning",
        TimesheetStatus.APPROVED: "success",
        TimesheetStatus.REOPENED: "danger",
    }

    return render_template(
        "timesheets/list.html",
        projects=projects,
        selected_project_id=project_id,
        selected_date=date,
        selected_status=status,
        timesheets=timesheets,
        statuses=TimesheetStatus,
        status_colors=status_colors,
        UserRole=UserRole,
    )


@app.route("/timesheets/new", methods=["GET", "POST"])
@login_required
def web_create_timesheet():
    if request.method == "POST":
        project_id = request.form.get("project_id", type=int)
        crew_id = request.form.get("crew_id", type=int)
        date = request.form.get("date")
        action = request.form.get("action")

        # Create timesheet
        timesheet = Timesheet(
            project_id=project_id,
            crew_id=crew_id,
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            submitted_by=current_user.id,
        )

        db.session.add(timesheet)

        # Add entries
        user_ids = request.form.getlist("user_ids[]")
        cost_code_ids = request.form.getlist("cost_code_ids[]")
        hours = request.form.getlist("hours[]")
        overtime_hours = request.form.getlist("overtime_hours[]")

        for i in range(len(user_ids)):
            entry = TimesheetEntry(
                timesheet=timesheet,
                user_id=user_ids[i],
                cost_code_id=cost_code_ids[i],
                hours=float(hours[i]),
                overtime_hours=float(overtime_hours[i]),
            )
            db.session.add(entry)

        if action == "submit":
            timesheet.status = TimesheetStatus.PENDING_SUPER
            timesheet.submitted_at = datetime.utcnow()
            flash("Timesheet submitted for approval.", "success")
        else:
            flash("Timesheet saved as draft.", "success")

        db.session.commit()
        return redirect(url_for("timesheet_list"))

    projects = Project.query.filter_by(is_active=True).all()
    crews = Crew.query.filter_by(is_active=True).all()

    return render_template("timesheets/entry.html", projects=projects, crews=crews)


@app.route("/timesheets/<int:timesheet_id>")
@login_required
def view_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    status_colors = {
        TimesheetStatus.DRAFT: "secondary",
        TimesheetStatus.PENDING_SUPER: "info",
        TimesheetStatus.PENDING_PM: "primary",
        TimesheetStatus.PENDING_PAYROLL: "warning",
        TimesheetStatus.APPROVED: "success",
        TimesheetStatus.REOPENED: "danger",
    }
    return render_template(
        "timesheets/view.html",
        timesheet=timesheet,
        status_colors=status_colors,
        TimesheetStatus=TimesheetStatus,
        UserRole=UserRole,
    )


@app.route("/timesheets/bulk-approve", methods=["GET", "POST"])
@login_required
def bulk_approve_timesheets():
    # Get user's role
    user_role = current_user.role

    # Determine which timesheets the user can approve based on their role
    if user_role == UserRole.SUPERINTENDENT:
        query = Timesheet.query.filter_by(status=TimesheetStatus.PENDING_SUPER)
    elif user_role == UserRole.PROJECT_MANAGER:
        query = Timesheet.query.filter(
            Timesheet.status.in_(
                [TimesheetStatus.PENDING_SUPER, TimesheetStatus.PENDING_PM]
            )
        )
    elif user_role == UserRole.PAYROLL:
        query = Timesheet.query.filter(
            Timesheet.status.in_([TimesheetStatus.PENDING_PAYROLL])
        )
    elif user_role == UserRole.ADMIN:
        # Admins can see all non-draft timesheets that can be approved
        query = Timesheet.query.filter(
            Timesheet.status.in_(
                [
                    TimesheetStatus.PENDING_SUPER,
                    TimesheetStatus.PENDING_PM,
                    TimesheetStatus.PENDING_PAYROLL,
                ]
            )
        )
    else:
        flash("You don't have permission to approve timesheets.", "danger")
        return redirect(url_for("timesheet_list"))

    if request.method == "POST":
        timesheet_ids = request.form.getlist("timesheet_ids[]")
        comments = request.form.get("comments", "")
        success_count = 0
        error_messages = []

        for timesheet_id in timesheet_ids:
            try:
                timesheet = Timesheet.query.get(timesheet_id)
                if not timesheet:
                    error_messages.append(f"Timesheet {timesheet_id} not found")
                    continue

                # Determine next status based on current status and user role
                status_transitions = {
                    TimesheetStatus.PENDING_SUPER: {
                        UserRole.SUPERINTENDENT: TimesheetStatus.PENDING_PM,
                        UserRole.PROJECT_MANAGER: TimesheetStatus.APPROVED,  # PM can approve directly
                        UserRole.ADMIN: TimesheetStatus.PENDING_PM,
                    },
                    TimesheetStatus.PENDING_PM: {
                        UserRole.PROJECT_MANAGER: TimesheetStatus.PENDING_PAYROLL,
                        UserRole.ADMIN: TimesheetStatus.PENDING_PAYROLL,
                    },
                    TimesheetStatus.PENDING_PAYROLL: {
                        UserRole.PAYROLL: TimesheetStatus.APPROVED,
                        UserRole.ADMIN: TimesheetStatus.APPROVED,
                    },
                }

                if timesheet.status not in status_transitions:
                    error_messages.append(
                        f"Timesheet {timesheet_id} cannot be approved in its current status"
                    )
                    continue

                if user_role not in status_transitions[timesheet.status]:
                    error_messages.append(
                        f"You don't have permission to approve timesheet {timesheet_id}"
                    )
                    continue

                # Update status
                timesheet.status = status_transitions[timesheet.status][user_role]

                # Create approval record
                approval = Approval(
                    timesheet_id=timesheet_id,
                    approver_id=current_user.id,
                    action=ApprovalAction.APPROVE,
                    comments=comments,
                )

                db.session.add(approval)
                success_count += 1

            except Exception as e:
                error_messages.append(
                    f"Error processing timesheet {timesheet_id}: {str(e)}"
                )
                continue

        db.session.commit()

        if success_count > 0:
            flash(f"Successfully approved {success_count} timesheets", "success")
        if error_messages:
            for msg in error_messages:
                flash(msg, "danger")

        return redirect(url_for("timesheet_list"))

        # GET request - show bulk approval form
    timesheets = query.order_by(Timesheet.date.desc()).all()

    status_colors = {
        TimesheetStatus.DRAFT: "secondary",
        TimesheetStatus.PENDING_SUPER: "info",
        TimesheetStatus.PENDING_PM: "primary",
        TimesheetStatus.PENDING_PAYROLL: "warning",
        TimesheetStatus.APPROVED: "success",
        TimesheetStatus.REOPENED: "danger",
    }

    return render_template(
        "timesheets/bulk_approve.html",
        timesheets=timesheets,
        status_colors=status_colors,
        UserRole=UserRole,
    )


@app.route("/timesheets/submit-all", methods=["POST"])
@login_required
def submit_all_draft_timesheets():
    # Find all draft timesheets
    draft_timesheets = Timesheet.query.filter_by(status=TimesheetStatus.DRAFT).all()

    success_count = 0
    for timesheet in draft_timesheets:
        try:
            # Update status
            timesheet.status = TimesheetStatus.PENDING_SUPER
            timesheet.submitted_at = datetime.utcnow()

            # Create approval record
            approval = Approval(
                timesheet_id=timesheet.id,
                approver_id=current_user.id,
                action=ApprovalAction.SUBMIT,
                comments="Submitted via bulk submit",
            )
            db.session.add(approval)
            success_count += 1
        except Exception as e:
            flash(f"Error submitting timesheet {timesheet.id}: {str(e)}", "danger")

    db.session.commit()
    flash(f"Successfully submitted {success_count} timesheets for approval", "success")
    return redirect(url_for("timesheet_list"))


@app.route("/timesheets/<int:timesheet_id>/approve", methods=["POST"])
@login_required
def approve_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)
    comments = request.form.get("comments", "")
    user_role = current_user.role

    # Determine next status based on current status and user role
    status_transitions = {
        TimesheetStatus.PENDING_SUPER: {
            UserRole.SUPERINTENDENT: TimesheetStatus.PENDING_PM,
            UserRole.PROJECT_MANAGER: TimesheetStatus.APPROVED,  # PM can approve directly
            UserRole.ADMIN: TimesheetStatus.PENDING_PM,
        },
        TimesheetStatus.PENDING_PM: {
            UserRole.PROJECT_MANAGER: TimesheetStatus.PENDING_PAYROLL,
            UserRole.ADMIN: TimesheetStatus.PENDING_PAYROLL,
        },
        TimesheetStatus.PENDING_PAYROLL: {
            UserRole.PAYROLL: TimesheetStatus.APPROVED,
            UserRole.ADMIN: TimesheetStatus.APPROVED,
        },
    }

    if timesheet.status not in status_transitions:
        flash("Timesheet cannot be approved in its current status", "danger")
        return redirect(url_for("view_timesheet", timesheet_id=timesheet_id))

    if user_role not in status_transitions[timesheet.status]:
        flash("You don't have permission to approve this timesheet", "danger")
        return redirect(url_for("view_timesheet", timesheet_id=timesheet_id))

    # Update status
    timesheet.status = status_transitions[timesheet.status][user_role]

    # Create approval record
    approval = Approval(
        timesheet_id=timesheet_id,
        approver_id=current_user.id,
        action=ApprovalAction.APPROVE,
        comments=comments,
    )

    db.session.add(approval)
    db.session.commit()

    flash("Timesheet approved successfully", "success")
    return redirect(url_for("view_timesheet", timesheet_id=timesheet_id))


@app.route("/timesheets/<int:timesheet_id>/edit", methods=["GET", "POST"])
@login_required
def edit_timesheet(timesheet_id):
    timesheet = Timesheet.query.get_or_404(timesheet_id)

    if timesheet.status != TimesheetStatus.DRAFT:
        flash("Only draft timesheets can be edited.", "danger")
        return redirect(url_for("timesheet_list"))

    if request.method == "POST":
        action = request.form.get("action")

        # Update entries
        user_ids = request.form.getlist("user_ids[]")
        cost_code_ids = request.form.getlist("cost_code_ids[]")
        hours = request.form.getlist("hours[]")
        overtime_hours = request.form.getlist("overtime_hours[]")

        # Remove existing entries
        for entry in timesheet.entries:
            db.session.delete(entry)

        # Add new entries
        for i in range(len(user_ids)):
            entry = TimesheetEntry(
                timesheet=timesheet,
                user_id=user_ids[i],
                cost_code_id=cost_code_ids[i],
                hours=float(hours[i]),
                overtime_hours=float(overtime_hours[i]),
            )
            db.session.add(entry)

        if action == "submit":
            timesheet.status = TimesheetStatus.PENDING_SUPER
            timesheet.submitted_at = datetime.utcnow()
            flash("Timesheet submitted for approval.", "success")
        else:
            flash("Timesheet updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("timesheet_list"))

    projects = Project.query.filter_by(is_active=True).all()
    crews = Crew.query.filter_by(is_active=True).all()
    crew_members = (
        User.query.join(CrewMember)
        .filter(CrewMember.crew_id == timesheet.crew_id, CrewMember.is_active == True)
        .all()
    )
    cost_codes = CostCode.query.filter_by(
        project_id=timesheet.project_id, is_active=True
    ).all()

    return render_template(
        "timesheets/entry.html",
        timesheet=timesheet,
        projects=projects,
        crews=crews,
        crew_members=crew_members,
        cost_codes=cost_codes,
    )


def get_labor_summary(project_id=None, date_from=None, date_to=None):
    query = (
        db.session.query(
            CostCode.code,
            CostCode.description,
            CostCode.phase,
            CostCode.budget_hours,
            Project.name.label("project_name"),
            db.func.sum(TimesheetEntry.hours).label("actual_hours"),
            db.func.sum(TimesheetEntry.overtime_hours).label("overtime_hours"),
        )
        .join(Project, CostCode.project_id == Project.id)
        .join(TimesheetEntry, CostCode.id == TimesheetEntry.cost_code_id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .filter(Timesheet.status == TimesheetStatus.APPROVED)
    )

    if project_id:
        query = query.filter(CostCode.project_id == project_id)

    if date_from:
        query = query.filter(
            Timesheet.date >= datetime.strptime(date_from, "%Y-%m-%d").date()
        )

    if date_to:
        query = query.filter(
            Timesheet.date <= datetime.strptime(date_to, "%Y-%m-%d").date()
        )

    results = query.group_by(
        CostCode.id,
        CostCode.code,
        CostCode.description,
        CostCode.phase,
        CostCode.budget_hours,
        Project.name,
    ).all()

    summary = []
    for result in results:
        actual_hours = float(result.actual_hours or 0)
        budget_hours = float(result.budget_hours or 0)
        variance = actual_hours - budget_hours
        variance_pct = (variance / budget_hours * 100) if budget_hours > 0 else 0

        summary.append(
            {
                "cost_code": f"{result.code} ({result.project_name})",
                "description": result.description,
                "phase": result.phase,
                "budget_hours": budget_hours,
                "actual_hours": actual_hours,
                "overtime_hours": float(result.overtime_hours or 0),
                "variance": variance,
                "variance_percentage": round(variance_pct, 2),
                "utilization": round((actual_hours / budget_hours * 100), 2)
                if budget_hours > 0
                else 0,
            }
        )

    return summary


# Enums
class UserRole(Enum):
    WORKER = "worker"
    CREW_ADMIN = "crew_admin"
    SUPERINTENDENT = "superintendent"
    PROJECT_MANAGER = "project_manager"
    PAYROLL = "payroll"
    ADMIN = "admin"


class TimesheetStatus(Enum):
    DRAFT = "draft"
    PENDING_SUPER = "pending_superintendent"
    PENDING_PM = "pending_pm"
    PENDING_PAYROLL = "pending_payroll"
    APPROVED = "approved"
    REOPENED = "reopened"


class ApprovalAction(Enum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    REOPEN = "reopen"


# Models
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.WORKER)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    crew_memberships = db.relationship("CrewMember", back_populates="user")
    timesheet_entries = db.relationship("TimesheetEntry", back_populates="user")
    approvals = db.relationship("Approval", back_populates="approver")


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    budget_hours = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    crews = db.relationship("Crew", back_populates="project")
    cost_codes = db.relationship("CostCode", back_populates="project")
    timesheets = db.relationship("Timesheet", back_populates="project")


class Crew(db.Model):
    __tablename__ = "crews"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    project = db.relationship("Project", back_populates="crews")
    supervisor = db.relationship("User")
    members = db.relationship("CrewMember", back_populates="crew")
    timesheets = db.relationship("Timesheet", back_populates="crew")


class CrewMember(db.Model):
    __tablename__ = "crew_members"

    id = db.Column(db.Integer, primary_key=True)
    crew_id = db.Column(db.Integer, db.ForeignKey("crews.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    join_date = db.Column(db.Date, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    crew = db.relationship("Crew", back_populates="members")
    user = db.relationship("User", back_populates="crew_memberships")


class CostCode(db.Model):
    __tablename__ = "cost_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    phase = db.Column(db.String(100))
    activity = db.Column(db.String(100))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    budget_hours = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    project = db.relationship("Project", back_populates="cost_codes")
    timesheet_entries = db.relationship("TimesheetEntry", back_populates="cost_code")


class Timesheet(db.Model):
    __tablename__ = "timesheets"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    crew_id = db.Column(db.Integer, db.ForeignKey("crews.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(TimesheetStatus), default=TimesheetStatus.DRAFT)
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    submitted_at = db.Column(db.DateTime)
    version = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project = db.relationship("Project", back_populates="timesheets")
    crew = db.relationship("Crew", back_populates="timesheets")
    submitter = db.relationship("User")
    entries = db.relationship(
        "TimesheetEntry", back_populates="timesheet", cascade="all, delete-orphan"
    )
    approvals = db.relationship("Approval", back_populates="timesheet")
    versions = db.relationship("TimesheetVersion", back_populates="timesheet")

    @property
    def total_hours(self):
        """Calculate total hours (regular + overtime) for all entries in this timesheet."""
        return sum(entry.hours + entry.overtime_hours for entry in self.entries)

    @property
    def entry_count(self):
        """Get the number of entries in this timesheet."""
        return len(self.entries)


class TimesheetEntry(db.Model):
    __tablename__ = "timesheet_entries"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey("timesheets.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cost_code_id = db.Column(db.Integer, db.ForeignKey("cost_codes.id"), nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    hours = db.Column(db.Float, nullable=False)
    overtime_hours = db.Column(db.Float, default=0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    timesheet = db.relationship("Timesheet", back_populates="entries")
    user = db.relationship("User", back_populates="timesheet_entries")
    cost_code = db.relationship("CostCode", back_populates="timesheet_entries")


class Approval(db.Model):
    __tablename__ = "approvals"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey("timesheets.id"), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.Enum(ApprovalAction), nullable=False)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    timesheet = db.relationship("Timesheet", back_populates="approvals")
    approver = db.relationship("User", back_populates="approvals")


class TimesheetVersion(db.Model):
    __tablename__ = "timesheet_versions"

    id = db.Column(db.Integer, primary_key=True)
    timesheet_id = db.Column(db.Integer, db.ForeignKey("timesheets.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    data_snapshot = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    timesheet = db.relationship("Timesheet", back_populates="versions")
    creator = db.relationship("User")


# Authentication Routes
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = User.query.filter_by(username=username, is_active=True).first()

    if user and check_password_hash(user.password_hash, password):
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                "role": user.role.value,
                "username": user.username,
                "full_name": f"{user.first_name} {user.last_name}",
            },
        )
        return jsonify(
            {
                "access_token": access_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role.value,
                    "full_name": f"{user.first_name} {user.last_name}",
                },
            }
        )

    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/api/auth/register", methods=["POST"])
@jwt_required()
def register():
    # Only admins can register new users
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if current_user.role != UserRole.ADMIN:
        return jsonify({"error": "Insufficient permissions"}), 403

    data = request.get_json()

    # Validate required fields
    required_fields = [
        "username",
        "email",
        "password",
        "first_name",
        "last_name",
        "role",
    ]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    # Check if user already exists
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already exists"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 400

    # Create new user
    user = User(
        username=data["username"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        first_name=data["first_name"],
        last_name=data["last_name"],
        role=UserRole(data["role"]),
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User created successfully", "user_id": user.id}), 201


# Timesheet Routes
@app.route("/api/timesheets", methods=["GET"])
@jwt_required()
def get_timesheets():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    # Query parameters
    project_id = request.args.get("project_id")
    date = request.args.get("date")
    status = request.args.get("status")

    query = Timesheet.query

    # Filter based on user role
    if current_user.role == UserRole.WORKER:
        # Workers can only see timesheets for crews they're part of
        crew_ids = [cm.crew_id for cm in current_user.crew_memberships if cm.is_active]
        query = query.filter(Timesheet.crew_id.in_(crew_ids))

    # Apply filters
    if project_id:
        query = query.filter(Timesheet.project_id == project_id)
    if date:
        query = query.filter(Timesheet.date == date)
    if status:
        query = query.filter(Timesheet.status == TimesheetStatus(status))

    timesheets = query.order_by(Timesheet.date.desc()).all()

    return jsonify(
        [
            {
                "id": ts.id,
                "project": {"id": ts.project.id, "name": ts.project.name},
                "crew": {"id": ts.crew.id, "name": ts.crew.name},
                "date": ts.date.isoformat(),
                "status": ts.status.value,
                "total_hours": sum(entry.hours for entry in ts.entries),
                "entry_count": len(ts.entries),
                "submitted_at": ts.submitted_at.isoformat()
                if ts.submitted_at
                else None,
                "version": ts.version,
            }
            for ts in timesheets
        ]
    )


@app.route("/api/timesheets", methods=["POST"])
@jwt_required()
def api_create_timesheet():
    current_user_id = get_jwt_identity()
    data = request.get_json()

    # Validate required fields
    required_fields = ["project_id", "crew_id", "date"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    # Check if timesheet already exists for this crew and date
    existing = Timesheet.query.filter_by(
        project_id=data["project_id"],
        crew_id=data["crew_id"],
        date=datetime.strptime(data["date"], "%Y-%m-%d").date(),
    ).first()

    if existing:
        return jsonify(
            {"error": "Timesheet already exists for this crew and date"}
        ), 400

    # Create timesheet
    timesheet = Timesheet(
        project_id=data["project_id"],
        crew_id=data["crew_id"],
        date=datetime.strptime(data["date"], "%Y-%m-%d").date(),
        submitted_by=current_user_id,
    )

    db.session.add(timesheet)
    db.session.commit()

    return jsonify(
        {"id": timesheet.id, "message": "Timesheet created successfully"}
    ), 201


@app.route("/api/timesheets/<int:timesheet_id>/entries", methods=["POST"])
@jwt_required()
def add_timesheet_entry():
    current_user_id = get_jwt_identity()
    timesheet_id = request.route["timesheet_id"]
    data = request.get_json()

    timesheet = Timesheet.query.get_or_404(timesheet_id)

    # Check if timesheet is editable
    if timesheet.status == TimesheetStatus.APPROVED:
        return jsonify({"error": "Cannot modify approved timesheet"}), 400

    # Validate required fields
    required_fields = ["user_id", "cost_code_id", "hours"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    # Create entry
    entry = TimesheetEntry(
        timesheet_id=timesheet_id,
        user_id=data["user_id"],
        cost_code_id=data["cost_code_id"],
        hours=data["hours"],
        overtime_hours=data.get("overtime_hours", 0),
        description=data.get("description", ""),
        start_time=datetime.fromisoformat(data["start_time"])
        if data.get("start_time")
        else None,
        end_time=datetime.fromisoformat(data["end_time"])
        if data.get("end_time")
        else None,
    )

    db.session.add(entry)
    db.session.commit()

    return jsonify({"id": entry.id, "message": "Entry added successfully"}), 201


@app.route("/api/timesheets/<int:timesheet_id>/submit", methods=["POST"])
@jwt_required()
def submit_timesheet():
    current_user_id = get_jwt_identity()
    timesheet_id = request.route["timesheet_id"]

    timesheet = Timesheet.query.get_or_404(timesheet_id)

    if timesheet.status != TimesheetStatus.DRAFT:
        return jsonify({"error": "Only draft timesheets can be submitted"}), 400

    if not timesheet.entries:
        return jsonify({"error": "Cannot submit empty timesheet"}), 400

    # Create snapshot for versioning
    snapshot = {
        "entries": [
            {
                "user_id": entry.user_id,
                "cost_code_id": entry.cost_code_id,
                "hours": entry.hours,
                "overtime_hours": entry.overtime_hours,
                "description": entry.description,
                "start_time": entry.start_time.isoformat()
                if entry.start_time
                else None,
                "end_time": entry.end_time.isoformat() if entry.end_time else None,
            }
            for entry in timesheet.entries
        ],
        "status": timesheet.status.value,
        "submitted_at": datetime.utcnow().isoformat(),
    }

    version = TimesheetVersion(
        timesheet_id=timesheet_id,
        version_number=timesheet.version,
        data_snapshot=snapshot,
        created_by=current_user_id,
    )

    # Update timesheet status
    timesheet.status = TimesheetStatus.PENDING_SUPER
    timesheet.submitted_at = datetime.utcnow()

    # Create approval record
    approval = Approval(
        timesheet_id=timesheet_id,
        approver_id=current_user_id,
        action=ApprovalAction.SUBMIT,
        comments="Timesheet submitted for approval",
    )

    db.session.add(version)
    db.session.add(approval)
    db.session.commit()

    return jsonify({"message": "Timesheet submitted successfully"})


@app.route("/api/timesheets/<int:timesheet_id>/approve", methods=["POST"])
@jwt_required()
def api_approve_timesheet():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    timesheet_id = request.route["timesheet_id"]
    data = request.get_json()

    timesheet = Timesheet.query.get_or_404(timesheet_id)

    # Determine next status based on current status and user role
    status_transitions = {
        TimesheetStatus.PENDING_SUPER: {
            UserRole.SUPERINTENDENT: TimesheetStatus.PENDING_PM,
            UserRole.PROJECT_MANAGER: TimesheetStatus.APPROVED,  # PM can approve directly
        },
        TimesheetStatus.PENDING_PM: {
            UserRole.PROJECT_MANAGER: TimesheetStatus.PENDING_PAYROLL
        },
        TimesheetStatus.PENDING_PAYROLL: {UserRole.PAYROLL: TimesheetStatus.APPROVED},
    }

    if timesheet.status not in status_transitions:
        return jsonify({"error": "Timesheet cannot be approved in current status"}), 400

    if current_user.role not in status_transitions[timesheet.status]:
        return jsonify(
            {"error": "Insufficient permissions to approve this timesheet"}
        ), 403

    # Update status
    timesheet.status = status_transitions[timesheet.status][current_user.role]

    # Create approval record
    approval = Approval(
        timesheet_id=timesheet_id,
        approver_id=current_user_id,
        action=ApprovalAction.APPROVE,
        comments=data.get("comments", ""),
    )

    db.session.add(approval)
    db.session.commit()

    return jsonify(
        {
            "message": "Timesheet approved successfully",
            "new_status": timesheet.status.value,
        }
    )


# Dashboard Routes
@app.route("/api/dashboard/labor-summary")
@jwt_required()
def labor_summary():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    project_id = request.args.get("project_id")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    # Build query
    query = (
        db.session.query(
            CostCode.code,
            CostCode.description,
            CostCode.phase,
            CostCode.budget_hours,
            db.func.sum(TimesheetEntry.hours).label("actual_hours"),
            db.func.sum(TimesheetEntry.overtime_hours).label("overtime_hours"),
        )
        .join(TimesheetEntry, CostCode.id == TimesheetEntry.cost_code_id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .filter(Timesheet.status != TimesheetStatus.DRAFT)
    )

    if project_id:
        query = query.filter(CostCode.project_id == project_id)

    if date_from:
        query = query.filter(
            Timesheet.date >= datetime.strptime(date_from, "%Y-%m-%d").date()
        )

    if date_to:
        query = query.filter(
            Timesheet.date <= datetime.strptime(date_to, "%Y-%m-%d").date()
        )

    results = query.group_by(
        CostCode.id,
        CostCode.code,
        CostCode.description,
        CostCode.phase,
        CostCode.budget_hours,
    ).all()

    summary = []
    for result in results:
        actual_hours = float(result.actual_hours or 0)
        budget_hours = float(result.budget_hours or 0)
        variance = actual_hours - budget_hours
        variance_pct = (variance / budget_hours * 100) if budget_hours > 0 else 0

        summary.append(
            {
                "cost_code": result.code,
                "description": result.description,
                "phase": result.phase,
                "budget_hours": budget_hours,
                "actual_hours": actual_hours,
                "overtime_hours": float(result.overtime_hours or 0),
                "variance": variance,
                "variance_percentage": round(variance_pct, 2),
                "utilization": round((actual_hours / budget_hours * 100), 2)
                if budget_hours > 0
                else 0,
            }
        )

    return jsonify(summary)


@app.route("/api/projects/<int:project_id>/cost-codes")
@login_required
def get_project_cost_codes(project_id):
    cost_codes = (
        CostCode.query.filter_by(project_id=project_id, is_active=True)
        .order_by(CostCode.code)
        .all()
    )

    return jsonify(
        [
            {
                "id": cc.id,
                "code": cc.code,
                "description": cc.description,
                "phase": cc.phase,
                "activity": cc.activity,
                "budget_hours": cc.budget_hours,
            }
            for cc in cost_codes
        ]
    )


@app.route("/api/crews/<int:crew_id>/members")
@login_required
def get_crew_members(crew_id):
    crew = Crew.query.get_or_404(crew_id)
    members = [
        member.user
        for member in crew.members
        if member.is_active and member.user.is_active
    ]
    return jsonify(
        [
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }
            for user in members
        ]
    )


# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({"error": "Internal server error"}), 500


# Initialize database
def init_db():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    init_db()  # Initialize database before running the app
    app.run(debug=True, host="0.0.0.0", port=5000)


# Admin Routes
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return redirect(url_for("user_list"))


@app.route("/admin/projects")
@login_required
@admin_required
def admin_projects():
    projects = Project.query.order_by(Project.name).all()
    return render_template(
        "admin/projects.html", projects=projects, active_page="projects"
    )


@app.route("/admin/projects/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_project():
    if request.method == "POST":
        project = Project(
            name=request.form["name"],
            code=request.form["code"],
            description=request.form.get("description", ""),
            start_date=datetime.strptime(request.form["start_date"], "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            if request.form.get("end_date")
            else None,
            budget_hours=float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0,
            is_active=True,
        )
        db.session.add(project)
        db.session.commit()
        flash("Project created successfully", "success")
        return redirect(url_for("admin_projects"))

    return render_template("admin/project_form.html", active_page="projects")


@app.route("/admin/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == "POST":
        project.name = request.form["name"]
        project.code = request.form["code"]
        project.description = request.form.get("description", "")
        project.start_date = datetime.strptime(
            request.form["start_date"], "%Y-%m-%d"
        ).date()
        project.end_date = (
            datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()
            if request.form.get("end_date")
            else None
        )
        project.budget_hours = (
            float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0
        )
        project.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Project updated successfully", "success")
        return redirect(url_for("admin_projects"))

    return render_template(
        "admin/project_form.html", project=project, active_page="projects"
    )


@app.route("/admin/crews")
@login_required
@admin_required
def admin_crews():
    crews = Crew.query.order_by(Crew.name).all()
    return render_template("admin/crews.html", crews=crews, active_page="crews")


@app.route("/admin/crews/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_crew():
    if request.method == "POST":
        crew = Crew(
            name=request.form["name"],
            project_id=request.form["project_id"],
            supervisor_id=request.form["supervisor_id"],
            is_active=True,
        )
        db.session.add(crew)
        db.session.commit()

        # Add crew members
        member_ids = request.form.getlist("member_ids[]")
        for user_id in member_ids:
            member = CrewMember(crew_id=crew.id, user_id=int(user_id), is_active=True)
            db.session.add(member)

        db.session.commit()
        flash("Crew created successfully", "success")
        return redirect(url_for("admin_crews"))

    projects = Project.query.filter_by(is_active=True).all()
    supervisors = User.query.filter(
        User.role.in_([UserRole.CREW_ADMIN, UserRole.SUPERINTENDENT]),
        User.is_active == True,
    ).all()
    workers = User.query.filter_by(role=UserRole.WORKER, is_active=True).all()

    return render_template(
        "admin/crew_form.html",
        projects=projects,
        supervisors=supervisors,
        workers=workers,
        active_page="crews",
    )


@app.route("/admin/crews/<int:crew_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_crew(crew_id):
    crew = Crew.query.get_or_404(crew_id)
    if request.method == "POST":
        crew.name = request.form["name"]
        crew.project_id = request.form["project_id"]
        crew.supervisor_id = request.form["supervisor_id"]
        crew.is_active = bool(request.form.get("is_active"))

        # Update crew members
        CrewMember.query.filter_by(crew_id=crew.id).delete()
        member_ids = request.form.getlist("member_ids[]")
        for user_id in member_ids:
            member = CrewMember(crew_id=crew.id, user_id=int(user_id), is_active=True)
            db.session.add(member)

        db.session.commit()
        flash("Crew updated successfully", "success")
        return redirect(url_for("admin_crews"))

    projects = Project.query.filter_by(is_active=True).all()
    supervisors = User.query.filter(
        User.role.in_([UserRole.CREW_ADMIN, UserRole.SUPERINTENDENT]),
        User.is_active == True,
    ).all()
    workers = User.query.filter_by(role=UserRole.WORKER, is_active=True).all()
    current_members = [member.user_id for member in crew.members if member.is_active]

    return render_template(
        "admin/crew_form.html",
        crew=crew,
        projects=projects,
        supervisors=supervisors,
        workers=workers,
        current_members=current_members,
        active_page="crews",
    )


@app.route("/admin/cost-codes")
@login_required
@admin_required
def admin_cost_codes():
    cost_codes = CostCode.query.order_by(CostCode.project_id, CostCode.code).all()
    return render_template(
        "admin/cost_codes.html", cost_codes=cost_codes, active_page="cost_codes"
    )


@app.route("/admin/cost-codes/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_cost_code():
    if request.method == "POST":
        cost_code = CostCode(
            code=request.form["code"],
            description=request.form["description"],
            phase=request.form["phase"],
            activity=request.form["activity"],
            project_id=request.form["project_id"],
            budget_hours=float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0,
            is_active=True,
        )
        db.session.add(cost_code)
        db.session.commit()
        flash("Cost code created successfully", "success")
        return redirect(url_for("admin_cost_codes"))

    projects = Project.query.filter_by(is_active=True).all()
    return render_template(
        "admin/cost_code_form.html", projects=projects, active_page="cost_codes"
    )


@app.route("/admin/cost-codes/<int:cost_code_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_cost_code(cost_code_id):
    cost_code = CostCode.query.get_or_404(cost_code_id)
    if request.method == "POST":
        cost_code.code = request.form["code"]
        cost_code.description = request.form["description"]
        cost_code.phase = request.form["phase"]
        cost_code.activity = request.form["activity"]
        cost_code.project_id = request.form["project_id"]
        cost_code.budget_hours = (
            float(request.form["budget_hours"])
            if request.form.get("budget_hours")
            else 0
        )
        cost_code.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("Cost code updated successfully", "success")
        return redirect(url_for("admin_cost_codes"))

    projects = Project.query.filter_by(is_active=True).all()
    return render_template(
        "admin/cost_code_form.html",
        cost_code=cost_code,
        projects=projects,
        active_page="cost_codes",
    )
