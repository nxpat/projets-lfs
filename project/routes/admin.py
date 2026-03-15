# routes/admin.py
from flask import (
    Blueprint,
    current_app,
    Response,
    render_template,
    redirect,
    url_for,
    flash,
    send_file,
)
from sqlalchemy import case, func
from flask_login import login_required, current_user

from http import HTTPStatus

import pandas as pd

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from ..models import db, Personnel, Dashboard, Project, SchoolYear
from ..decorators import require_unlocked_db

from ..project import (
    SelectYearsForm,
    LockForm,
    DownloadForm,
    choices,
    levels,
    create_schoolyear_config_form,
)

from ..utils import (
    get_datetime,
    get_default_sy_dates,
    auto_dashboard,
    auto_school_year,
    get_years_choices,
    get_divisions,
    division_name,
    get_projects_df,
)

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

    personnels = Personnel.query.order_by(
        case(
            {role: index for index, role in enumerate(choices["role"])},
            value=Personnel.role,
            else_=len(choices["role"]),  # this will place empty roles at the end
        ),
        Personnel.name,
    ).all()

    return render_template("personnels.html", personnels=personnels, choices=choices)


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

    # Handle config form submission
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
    form = DownloadForm()
    form.sy.choices, form.fy.choices = get_years_choices(fy=True)

    if form.validate_on_submit():
        if current_user.p.role in ["gestion", "direction", "admin"]:
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
