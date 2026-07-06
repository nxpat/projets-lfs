# routes/admin.py
from flask import (
    Blueprint,
    current_app,
    Response,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    send_file,
    session,
    jsonify,
    abort,
)
from sqlalchemy import case, func
from flask_login import login_required, current_user

from http import HTTPStatus

import re
import os

import pandas as pd

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from ..models import db, Personnel, Dashboard, Project, ProjectMember, ProjectComment, SchoolYear
from ..decorators import require_unlocked_db

from ..project import (
    SelectYearsForm,
    LockForm,
    DownloadForm,
    choices,
    levels,
    create_schoolyear_config_form,
    AddPersonnelForm,
    RemovePersonnelForm,
    BudgetFilterForm,
)

from ..utils import (
    get_datetime,
    get_default_sy_dates,
    auto_dashboard,
    auto_school_year,
    get_years_choices,
    get_member_choices,
    get_divisions,
    division_name,
    get_projects_df,
    query_projects,
)

import logging

logger = logging.getLogger(__name__)

DOMAIN = os.getenv("DOMAIN")
PROVISEUR = os.getenv("PROVISEUR")
DIRECTEUR = os.getenv("DIRECTEUR")

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("core.index"))

    # get database status
    auto_dashboard()
    dash = Dashboard.query.first()
    lock = dash.lock

    # get school year
    sy_start, sy_end, sy = auto_school_year()
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    # get total number of projects
    n_projects = db.session.query(Project.id).count()

    # form for setting database status
    form = LockForm()

    # set database status
    if form.validate_on_submit():
        if current_user.p.role == "admin" or lock != 2:
            if form.lock.data == "Ouvert":
                lock = 0
                flash("La base est maintenant ouverte !", "info")
            elif current_user.p.role == "admin":
                lock = 2
                flash("La base est maintenant fermée.", "info")
                dash.lock_message = "La base est momentanément <strong>fermée pour maintenance</strong>. La consultation reste ouverte."
            else:
                lock = 1
                flash("La base est maintenant fermée.", "info")
                dash.lock_message = "<strong>La base des projets est fermée</strong> : la création et la modification des projets n'est plus possible. <br>La consultation des projets, la messagerie et les autres fonctionnalités sont disponibles."
            dash.lock = lock
            db.session.commit()
            if lock:
                logger.info(f"Database locked by {current_user.p.email}")
            else:
                logger.info(f"Database opened by {current_user.p.email}")
        else:
            flash(
                "<strong>Attention :</strong> la base est momentanément <strong>fermée pour maintenance</strong>. <br>Les modifications sont impossibles.",
                "danger",
            )

    # database status form data set to the opposite value to serve as a toogle button
    form.lock.data = "Fermé" if not lock else "Ouvert"

    # get Project data grouped by school_year and status
    results = (
        db.session.query(Project.school_year, Project.status, func.count(Project.id).label("count"))
        .group_by(Project.school_year, Project.status)
        .order_by(Project.school_year.desc())
        .all()
    )

    # Transform results for easy template rendering
    df = pd.DataFrame(results, columns=["school_year", "status", "count"])
    df["status"] = df["status"].replace({"validated-10": "validated-1"})

    # Pivot the data
    # index = rows, columns = status headers, values = the counts
    df = df.pivot_table(
        index="school_year",
        columns="status",
        values="count",
        fill_value=0,
        aggfunc="sum",
        margins=True,  # automatically adds 'All' row and column totals
        margins_name="Total",
    )
    # adjust school years in descending order, keep Total as last row
    df = df.drop(index=df.index[-1]).sort_index(ascending=False)._append(df.iloc[-1])

    # complete with eventually missing columns
    statuses = ["draft", "ready-1", "validated-1", "ready", "validated", "rejected"]
    for status in statuses:
        if status not in df.columns:
            df[status] = 0

    # adjust status columns order
    df = df[statuses + ["Total"]]

    # Personnel statistics
    role_counts_raw = (
        db.session.query(Personnel.role, func.count(Personnel.id)).group_by(Personnel.role).all()
    )

    personnel_stats = {"direction": 0, "gestion": 0, "admin": 0, "user": 0, "inactive": 0}
    for role, count in role_counts_raw:
        if role in personnel_stats:
            personnel_stats[role] = count

    personnel_stats["total"] = sum(personnel_stats.values())

    # form for downloading the project database
    form2 = DownloadForm()
    form2.sy.choices, form2.fy.choices = get_years_choices(fy=True)
    form2.sy.data = sy
    form2.fy.data = str(datetime.now().year)

    # form for configuring the school year
    form3 = SelectYearsForm()
    form3.years.choices = [sy_next, sy]
    form3.years.data = sy
    form3.submit.label.text = "Modifier"

    # get divisions information for the current school year
    divisions = get_divisions(sy)
    division_data = {}
    for section in ["Lycée", "Collège", "Élémentaire", "Maternelle"]:
        division_data[section] = {}
        for level in levels[section]:
            count = sum(div.startswith(level) for div in divisions)
            if count:
                division_data[section][division_name(level)] = count
    division_data["Total"] = f"{len(divisions)} divisions"

    return render_template(
        "dashboard.html",
        form=form,
        form2=form2,
        form3=form3,
        n_projects=n_projects,
        lock=lock,
        df=df,
        sy_start=sy_start,
        sy_end=sy_end,
        sy=sy,
        division_data=division_data,
        personnel_stats=personnel_stats,
    )


@admin_bp.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    # check for authorized user
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("core.index"))

    # get school year
    sy_start, sy_end, sy = auto_school_year()
    # set current and next school year labels
    sy_current = sy
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    ### school year tab ###
    form = SelectYearsForm()

    # set school year choices
    df = get_projects_df(draft=False, data="budget")
    form.years.choices = sorted([(s, s) for s in set(df["school_year"])], reverse=True)
    if not form.years.choices:
        form.years.choices = [(sy_current, sy_current)]

    if (sy_next, sy_next) in form.years.choices:
        form.years.choices.insert(1, ("recurring", "Projets récurrents"))
    else:
        form.years.choices.insert(0, ("recurring", "Projets récurrents"))

    ## get form POST data
    if form.validate_on_submit():
        sy = form.years.data
    else:
        sy = sy_current

    # set form default data
    form.years.data = sy

    ## filter DataFrame
    if sy == "recurring":
        dfs = df[(df["school_year"] == sy_current) & (df["is_recurring"] == "Oui")]
    else:
        dfs = df[df["school_year"] == sy]

    # recurring school year
    if sy == "recurring":
        sy = sy_current

    ### fiscal year tab ###
    form2 = SelectYearsForm()

    # set dynamic fiscal years choices
    form2.years.choices = sorted(
        [
            y
            for y in set(
                df["school_year"].str.split(" - ", expand=True).drop_duplicates().values.flatten()
            )
        ],
        reverse=True,
    )
    if not form2.years.choices:
        form2.years.choices = [str(sy_end.year), str(sy_start.year)]

    ## get form2 POST data
    if form2.validate_on_submit():
        fy = form2.years.data
        tabf = True
    else:
        fy = str(sy_start.year) if sy_start.year == datetime.now().year else str(sy_end.year)
        tabf = False

    # set form default data
    form2.years.data = fy

    ## filter DataFrame
    df1 = (
        df[df["school_year"].str.startswith(fy)]
        .drop(columns=[*choices["budget"]] + [b + "_2" for b in choices["budget"]])
        .rename(columns=lambda x: x.replace("_1", ""))
    )

    df2 = (
        df[df["school_year"].str.endswith(fy)]
        .drop(columns=[*choices["budget"]] + [b + "_1" for b in choices["budget"]])
        .rename(columns=lambda x: x.replace("_2", ""))
    )

    dff = pd.concat([df1, df2], axis=0)

    return render_template(
        "budget.html",
        choices=choices,
        dfs=dfs,
        sy=sy,
        form=form,
        form2=form2,
        dff=dff,
        tabf=tabf,
    )


@admin_bp.route("/dashboard/personnels", methods=["GET", "POST"])
@login_required
def dashboard_personnels():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("core.index"))

    role_priority = case(
        {"direction": 1, "gestion": 2, "admin": 3, "user": 4, "inactive": 5}, value=Personnel.role
    )

    personnels = Personnel.query.order_by(role_priority, Personnel.name.asc()).all()

    return render_template("personnels.html", personnels=personnels, choices=choices)


@admin_bp.route("/personnel/add", methods=["GET", "POST"])
@login_required
@require_unlocked_db(level=2)
def add_personnel():
    if current_user.p.role not in ["direction", "admin"]:
        return redirect(url_for("core.index"))

    form = AddPersonnelForm()

    if form.validate_on_submit():
        firstname = form.firstname.data.strip().title()
        lastname = form.name.data.strip().title()
        full_email = f"{form.email_username.data.strip().lower()}@{DOMAIN}"
        existing = Personnel.query.filter_by(email=full_email).first()
        if existing:
            flash(
                f"L'adresse {full_email} est déjà attribuée à {existing.name} {existing.firstname}.",
                "danger",
            )
        else:
            new_personnel = Personnel(
                firstname=firstname,
                name=lastname,
                email=full_email,
                department=form.department.data,
                role=form.role.data,
            )
            db.session.add(new_personnel)
            db.session.commit()
            flash(
                f"{new_personnel.firstname} {new_personnel.name} ({new_personnel.department}) <br>a été ajouté avec succès.",
                "info",
            )
            logger.info(
                f"New personnel ({new_personnel.firstname} {new_personnel.name}, {new_personnel.department}) added by {current_user.p.email}"
            )
            return redirect(url_for("admin.dashboard"))

    return render_template("add_personnel.html", form=form)


@admin_bp.route("/personnel/remove", methods=["GET", "POST"])
@login_required
@require_unlocked_db(level=2)
def remove_personnel():
    if current_user.p.role not in ["direction", "admin"]:
        return redirect(url_for("core.index"))

    form = RemovePersonnelForm()
    form.personnel_id.choices = get_member_choices()

    if form.validate_on_submit():
        personnel = Personnel.query.get(form.personnel_id.data)
        if not personnel:
            flash("Personnel introuvable.", "danger")
            return redirect(url_for("admin.dashboard"))

        # --- Renaming logic for Direction role ---
        prefix = personnel.email.split("@")[0]
        is_generic_dir = personnel.role == "direction" and prefix in [PROVISEUR, DIRECTEUR]

        if is_generic_dir:
            pattern = f"{prefix}_%"
            others = Personnel.query.filter(Personnel.email.like(pattern)).all()

            max_num = 0
            for p_other in others:
                match = re.search(rf"{prefix}_(\d+)@", p_other.email)
                if match:
                    max_num = max(max_num, int(match.group(1)))

            new_index = str(max_num + 1).zfill(2)
            old_email = personnel.email
            personnel.email = f"{prefix}_{new_index}@{DOMAIN}"
            personnel.role = "inactive"

            db.session.commit()
            flash(
                f"Compte de direction archivé : {old_email} est devenu {personnel.email}.", "info"
            )
            logger.info(
                f"Archived personnel ({personnel.firstname} {personnel.name}, Direction) by {current_user.p.email}"
            )
            return redirect(url_for("admin.dashboard"))

        # --- Other users ---
        # (Vérification si suppression totale ou soft delete sans renommage)
        can_hard_delete = not (
            personnel.projects  # Participant in a project ? (via junction table)
            or (
                personnel.user  # Created or commented a project ? (require a user account)
                and (
                    Project.query.filter_by(uid=personnel.user.id).first()
                    or ProjectComment.query.filter_by(uid=personnel.user.id).first()
                )
            )
        )

        if can_hard_delete:
            if personnel.user:
                db.session.delete(personnel.user)
            db.session.delete(personnel)
            flash(
                f"La fiche de {personnel.firstname} {personnel.name} ({personnel.department}) <br>a été supprimée avec succès (aucune activité détectée).",
                "info",
            )
            logger.info(
                f"Deleted personnel ({personnel.firstname} {personnel.name}, {personnel.department}) by {current_user.p.email}"
            )
        else:
            personnel.role = "inactive"
            flash(
                f"{personnel.firstname} {personnel.name} ({personnel.department}) <br>a été enregistré comme inactif avec succès (historique préservé).",
                "info",
            )
            logger.info(
                f"Archived personnel ({personnel.firstname} {personnel.name}, {personnel.department}) by {current_user.p.email}"
            )

        db.session.commit()
        return redirect(url_for("admin.dashboard"))

    return render_template("remove_personnel.html", form=form)


@admin_bp.route("/get_personnel_preview/<int:pid>")
@login_required
def get_personnel_preview(pid):
    if current_user.p.role not in ["direction", "admin"]:
        abort(403)

    personnel = Personnel.query.get_or_404(pid)
    user = personnel.user

    # Projects Created (Query project IDs)
    if user:
        created_query = db.session.query(Project.id).filter(Project.uid == user.id)
    else:
        created_query = db.session.query(Project.id).filter(db.false())  # returns nothing

    # Projects Joined as Member (Query project IDs)
    member_query = db.session.query(ProjectMember.project_id).filter(
        ProjectMember.pid == personnel.id
    )

    # Total count of unique projects the person is involved in
    # SQL UNION automatically removes duplicates
    projects_count = created_query.union(member_query).count()

    # 4. Comments
    comment_count = ProjectComment.query.filter_by(uid=user.id).count() if user else 0

    stats = {
        "total_projects": projects_count,
        "comments": comment_count,
        "total_activity": projects_count + comment_count,
    }

    return render_template("_personnel_preview.html", personnel=personnel, stats=stats)


@admin_bp.route("/dashboard/sy", methods=["GET", "POST"])
@login_required
@require_unlocked_db(level=2)
def manage_school_year():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("core.index"))

    # compute current/adjacent school years and defaults
    sy_start, sy_end, sy = auto_school_year()
    sy_start_default, sy_end_default = get_default_sy_dates()
    sy_auto = sy_start == sy_start_default and sy_end == sy_end_default

    # get divisions information for the current school year
    divisions = get_divisions(sy)
    division_data = {}
    for section in ["Lycée", "Collège", "Élémentaire", "Maternelle"]:
        for level in levels[section]:
            count = sum(div.startswith(level) for div in divisions)
            if count:
                division_data[level] = count

    # instantiate form
    SchoolYearConfigForm = create_schoolyear_config_form(levels)
    form = SchoolYearConfigForm()

    if form.validate_on_submit():
        updated = False

        # get dates
        sy_auto = form.sy_auto.data
        sy_start = form.sy_start.data
        sy_end = form.sy_end.data

        # update the database with the dates for the current school year
        auto_school_year(sy_start, sy_end)

        # update the start date of the next school year if it exists
        sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"
        next_school_year = SchoolYear.query.filter(SchoolYear.sy == sy_next).first()
        if next_school_year:
            if next_school_year.sy_start != sy_end + timedelta(1):
                next_school_year.sy_start = sy_end + timedelta(1)
                updated = True

        # get number of divisions per level
        divisions = []
        division_data = {}
        for section in ["Lycée", "Collège", "Élémentaire", "Maternelle"]:
            for level in levels[section]:
                field_name = f"level_{level.lower().replace(' ', '_')}"
                n = getattr(form, field_name).data or 0
                division_data[level] = int(n)
                if n == 1:
                    divisions += [level]
                elif n > 1:
                    divisions += [level + chr(65 + (i % 26)) for i in range(n)]

        new_divisions = ",".join(divisions)
        school_year = SchoolYear.query.filter(SchoolYear.sy == sy).first()
        # update the database with the divisions
        if school_year.divisions != new_divisions:
            school_year.divisions = new_divisions
            updated = True

        if updated:
            db.session.commit()
            logger.info(f"School year parameters updated by {current_user.p.email}")
            flash(
                f"Les nouveaux paramètres de l'année scolaire <strong>{sy}</strong> <br>ont été enregistrés avec succès !",
                "info",
            )

        return redirect(url_for("admin.dashboard"))

    # populate form with schoolyear data
    # dates
    form.sy.data = sy
    form.sy_start.data = sy_start
    form.sy_end.data = sy_end
    form.sy_auto.data = sy_auto

    sy_previous = f"{sy_start.year - 1} - {sy_end.year - 1}"
    previous_school_year = SchoolYear.query.filter(SchoolYear.sy == sy_previous).first()
    if previous_school_year:
        form.sy_start.render_kw = {
            "min": previous_school_year.sy_end + timedelta(1),
            "max": previous_school_year.sy_end + timedelta(1),
        }
        form.sy_end.render_kw = {
            "min": previous_school_year.sy_end + relativedelta(months=6),
            "max": previous_school_year.sy_end + relativedelta(months=18),
        }

    # divisions
    for section in ["Lycée", "Collège", "Élémentaire", "Maternelle"]:
        for level in levels[section]:
            field_name = f"level_{level.lower().replace(' ', '_')}"
            if level in division_data:
                getattr(form, field_name).data = division_data[level]
            else:
                getattr(form, field_name).data = 0

    return render_template("sy.html", form=form)


@admin_bp.route("/download", methods=["POST"])
@login_required
def download_data():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("core.index"))

    form = DownloadForm()
    form.sy.choices, form.fy.choices = get_years_choices(fy=True)

    if form.validate_on_submit():
        years = form.sy.data if form.selection_mode.data == "sy" else form.fy.data
        years = None if years == "Toutes les années" else years
        df = get_projects_df(years=years, data="Excel", labels=True)
        if not df.empty:
            date = get_datetime().strftime("%Y-%m-%d-%Hh%M")
            filename = f"Projets_LFS-{date}.xlsx"
            data_path = current_app.config["DATA_PATH"]
            filepath = data_path / filename
            df.to_excel(
                filepath,
                sheet_name="Projets pédagogiques LFS",
                columns=df.columns,
            )
            return send_file(filepath, as_attachment=True)

    return Response(status=HTTPStatus.NO_CONTENT)


@admin_bp.route("/manage_budgets", methods=["GET", "POST"])
@login_required
def manage_budgets():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("core.index"))

    # get school year
    _, _, sy = auto_school_year()

    ## filter selection
    form2 = BudgetFilterForm()

    if form2.validate_on_submit():
        session["budget-filter"] = form2.filter.data

    if "budget-filter" not in session:  # default
        session["budget-filter"] = "LFS"

    form2.filter.data = session["budget-filter"]

    # get school year choices
    form3 = SelectYearsForm()
    form3.years.choices = get_years_choices()
    schoolyears = len(form3.years.choices) > 1

    ## school year selection
    if form3.validate_on_submit():
        if form3.years.data == "Toutes les années":
            session["budget-sy"] = None
        else:
            session["budget-sy"] = form3.years.data

    if "budget-sy" not in session:
        session["budget-sy"] = sy

    form3.years.data = session["budget-sy"]

    # Build Project query
    query = query_projects(
        current_user, filter=session["budget-filter"], years=session["budget-sy"], with_budget=True
    )

    # Order by newest first
    query = query.order_by(Project.id.desc())

    # Get the base count
    base_count = query.count()

    # --- Pagination ---
    # Get the requested page (default to 1)
    page = request.args.get("page", 1, type=int)

    # Check if the user just selected a new pagination length
    per_page_request = request.args.get("per_page")

    if per_page_request:
        if per_page_request == "all":
            session["budget-per_page"] = "all"
        else:
            try:
                session["budget-per_page"] = int(per_page_request)
            except ValueError:
                session["budget-per_page"] = 20  # Fallback for invalid data

    # Retrieve the current preference (defaulting to 20)
    per_page = session.get("budget-per_page", 20)

    # Handle "all" case: use 1 if the query is empty to avoid crashes
    actual_per_page = max(1, base_count) if per_page == "all" else per_page

    # Paginate
    pagination = query.paginate(page=page, per_page=actual_per_page, error_out=False)

    if (page > pagination.pages and pagination.pages > 0) or page < 1:
        flash("La page demandée n'existe pas.", "danger")
        return redirect(url_for(".manage_budgets", page=1))

    # Extract the items for the current page
    projects = pagination.items

    # ------
    # Pull existing distinct budget strings for the auto-complete <datalist>
    distinct_budgets = (
        db.session.query(Project.budget_id)
        .filter(Project.budget_id.isnot(None), Project.budget_id != "")
        .distinct()
        .all()
    )
    existing_budget_ids = [b[0] for b in distinct_budgets]

    return render_template(
        "manage_budgets.html",
        projects=projects,
        pagination=pagination,
        existing_budget_ids=existing_budget_ids,
        form2=form2,
        form3=form3,
        schoolyears=schoolyears,
    )


@admin_bp.route("/api/project/<int:project_id>/update-budget", methods=["POST"])
@login_required
def update_budget_id(project_id):
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return jsonify({"status": "error", "message": "Non autorisé"}), HTTPStatus.FORBIDDEN

    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    if not data or "budget_id" not in data:
        return jsonify({"status": "error", "message": "Données invalides"}), HTTPStatus.BAD_REQUEST

    new_code = data["budget_id"].strip() if data["budget_id"] else ""

    # Data validation: or empty (to delete), of between 3 and 50 chars
    if len(new_code) > 0 and (len(new_code) < 3 or len(new_code) > 50):
        return jsonify(
            {
                "status": "error",
                "message": "Le code budgétaire doit comporter entre 3 et 50 caractères (ou être vide).",
            }
        ), HTTPStatus.BAD_REQUEST

    project.budget_id = new_code
    db.session.commit()

    return jsonify(
        {"status": "success", "project_id": project.id, "budget_id": project.budget_id or ""}
    )
