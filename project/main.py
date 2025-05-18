from flask import (
    Blueprint,
    session,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    make_response,
    send_file,
    Response,
    jsonify,
)

from flask_login import login_required, current_user

from sqlalchemy import case

from http import HTTPStatus

from .models import (
    Personnel,
    User,
    Project,
    ProjectMember,
    ProjectHistory,
    ProjectComment,
    Dashboard,
    SchoolYear,
)
from . import db, data_path, app_version, production_env, gmail_service
from ._version import __version__

from .projects import (
    ProjectForm,
    CommentForm,
    SelectProjectForm,
    LockForm,
    ProjectFilterForm,
    DownloadForm,
    SetSchoolYearForm,
    SelectSchoolYearForm,
    SelectFiscalYearForm,
    choices,
    axes,
    priorities,
)

from datetime import datetime, date, time
from zoneinfo import ZoneInfo
from babel.dates import format_date, format_datetime

import os

import pandas as pd
import pickle
import re

import logging

if gmail_service:
    from .communication import send_notification

import calendar

try:
    from .graphs import sunburst_chart, bar_chart, timeline_chart

    graph_module = True
except ImportError:
    graph_module = False

try:
    from .print import generate_fieldtrip_pdf

    matplotlib_module = True
except ImportError:
    matplotlib_module = False

AMBASSADE_EMAIL = os.getenv("AMBASSADE_EMAIL")
AUTHOR = os.getenv("AUTHOR")
REFERENT_NUMERIQUE_EMAIL = os.getenv("REFERENT_NUMERIQUE_EMAIL")
GITHUB_REPO = os.getenv("GITHUB_REPO")
LFS_LOGO = os.getenv("LFS_LOGO")
LFS_WEBSITE = os.getenv("LFS_WEBSITE")
APP_WEBSITE = os.getenv("APP_WEBSITE")
BOOMERANG_WEBSITE = os.getenv("BOOMERANG_WEBSITE")

# init logger
logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# basefilename to save projects data (pickle format)
projects_file = "projets"

# field trip PDF form filename
fieldtrip_pdf = "formulaire_sortie-<id>.pdf"


def auto_dashboard():
    """create default record if Dashboard is empty"""
    if not Dashboard.query.first():
        # set default database lock to open
        dash = Dashboard(lock=0)
        db.session.add(dash)
        db.session.commit()


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_date_fr(date, withdate=True, withtime=False):
    if isinstance(date, str):
        try:
            # remove microseconds and time zone information, then convert to datetime
            date = datetime.strptime(date.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            logger.info(f"Error with date: {e}")
            return "None"
    if not date or str(date) == "NaT":
        logger.info(f"Error with date: {date}")
        return "None"
    elif not withdate:
        return format_datetime(date, format="H'h'mm", locale="fr_FR")
    elif withtime:
        return (
            format_datetime(date, format="EEE d MMM yyyy H'h'mm", locale="fr_FR")
            .capitalize()
            .removesuffix(" 0h00")
        )
    else:
        return format_date(date, format="EEE d MMM yyyy", locale="fr_FR").capitalize()


def get_project_dates(start_date, end_date):
    if end_date.date() == start_date.date():
        if end_date.time() == start_date.time():
            return get_date_fr(start_date, withtime=True)
        else:
            return f"{get_date_fr(start_date, withtime=False)} de {get_date_fr(start_date, withdate=False)} à {get_date_fr(end_date, withdate=False)}"
    else:
        return f"Du {get_date_fr(start_date, withtime=True)}<br>au {get_date_fr(end_date, withtime=True)}"


def auto_school_year(sy_start=None, sy_end=None):
    today = get_datetime().date()

    # default dates
    sy_start_default = date(today.year - 1 if today.month < 9 else today.year, 9, 1)
    sy_end_default = date(today.year if today.month < 9 else today.year + 1, 8, 31)

    # check if arguments are valid dates for the current school year
    # modify with default dates otherwise
    if not sy_start or sy_start > today:
        sy_start = sy_start_default
    if not sy_end or sy_end < today:
        sy_end = sy_end_default

    if SchoolYear.query.first():
        # get school year
        school_years = SchoolYear.query.all()
        for school_year in school_years:
            _start = school_year.sy_start
            _end = school_year.sy_end
            sy = school_year.sy
            if today > _start and today < _end:
                if _start != sy_start or _end != sy_end:
                    school_year.sy_start = sy_start
                    school_year.sy_end = sy_end
                    db.session.commit()
                return school_year.sy_start, school_year.sy_end, sy

    # a school year was not found, so we add a new one
    sy = f"{sy_start.year} - {sy_end.year}"
    sy_current = SchoolYear(sy_start=sy_start, sy_end=sy_end, sy=sy)
    db.session.add(sy_current)
    db.session.commit()

    return sy_start, sy_end, sy


def get_name(pid=None, uid=None, option=None):
    if pid:
        personnel = Personnel.query.get(pid)
    elif uid:
        if isinstance(uid, str):
            uid = int(uid)
        personnel = Personnel.query.get(User.query.get(uid).pid)
    else:
        return "None"
    if personnel:
        if option and "s" in option:
            option = option.strip("s")
            if current_user.p.id == pid or current_user.id == uid:
                return "moi"
        if option == "nf":
            return f"{personnel.name} {personnel.firstname}"
        elif option == "f":
            return f"{personnel.firstname}"
        elif option == "n":
            return f"{personnel.name}"
        else:
            return f"{personnel.firstname} {personnel.name}"
    else:
        return "None"


def get_label(choice, field):
    """get the label for the field choice"""
    if field == "location":
        return next(
            iter([x[1] for x in ProjectForm().location.choices if x[0] == choice])
        )
    elif field == "requirement":
        return next(
            iter([x[1] for x in ProjectForm().requirement.choices if x[0] == choice])
        )
    else:
        return None


def get_member_choices():
    """Get list of members with departments for members input field in form"""
    return {
        department: [
            (f"{personnel.id}", f"{personnel.firstname} {personnel.name}")
            for personnel in Personnel.query.filter(Personnel.department == department)
            .order_by(Personnel.name)
            .all()
        ]
        for department in choices["departments"]
        if Personnel.query.filter(Personnel.department == department).all()
    }


def row_to_dict(row):
    """Convert a SQLAlchemy row to a dictionary."""
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def get_projects_df(filter=None, sy=None, draft=True, data=None, labels=False):
    """Convert Project table to DataFrame
    filter: department name, project id
    sy: school year, "current", "next"
    draft: include draft projects
    data: db (save Pickle file), Excel (save .xlsx file), data (for data page), budget (for budget page)
    labels: replace coded values with meaningfull values

    return: dataframe with projects data
    """
    # get school year
    sy_start, sy_end, sy_current = auto_school_year()
    # set next school year
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    # SQLAlchemy ORM query filter
    if isinstance(filter, str):
        projects = [
            row_to_dict(project)
            for project in Project.query.all()
            if filter in project.departments.split(",")
        ]
    elif isinstance(filter, int):
        project = Project.query.get(filter)
        projects = [row_to_dict(project)]
    else:
        projects = [row_to_dict(project) for project in Project.query.all()]

    # add and remove fields
    for p in projects:
        project = Project.query.get(p["id"])

        p["members"] = ",".join([str(member.pid) for member in project.members])

        if data == "Excel":
            p["created_by"] = project.uid
            del p["uid"]

        if data not in ["db", "Excel"]:
            p["pid"] = project.user.pid
            del p["uid"]
            p["has_budget"] = project.has_budget()
            p["nb_comments"] = len(project.comments)

            # last modification by members and last validation
            if project.status.startswith("validated"):
                history_entry = (
                    ProjectHistory.query.filter(ProjectHistory.project_id == project.id)
                    .filter(~ProjectHistory.status.startswith("validated"))
                    .order_by(ProjectHistory.updated_at.desc())
                    .first()
                )
                p["updated_at"] = history_entry.updated_at
                p["updated_by"] = history_entry.updated_by
                p["validated_at"] = project.updated_at
                p["validated_by"] = project.updated_by
            else:
                history_entry = (
                    ProjectHistory.query.filter(ProjectHistory.project_id == project.id)
                    .filter(ProjectHistory.status.startswith("validated"))
                    .order_by(ProjectHistory.updated_at.desc())
                    .first()
                )
                if history_entry:
                    p["validated_at"] = history_entry.updated_at
                    p["validated_by"] = history_entry.updated_by
                else:
                    p["validated_at"] = None
                    p["validated_by"] = None

    # adjust field values
    for project in projects:
        project["is_recurring"] = "Oui" if project["is_recurring"] else "Non"

    # set columns for DataFrame
    columns = Project.__table__.columns.keys()

    columns.insert(8, "members")

    if data == "Excel":
        columns.remove("uid")
        columns.insert(1, "created_by")

    if data not in ["db", "Excel"]:
        columns.remove("uid")
        columns.insert(1, "pid")
        columns.append("has_budget")
        columns.append("nb_comments")
        columns.append("created_at")
        columns.append("validated_at")
        columns.append("validated_by")

    # convert SQLAlchemy ORM query result to a pandas DataFrame
    df = pd.DataFrame(projects, columns=columns)

    # set Id column as index
    if data != "db":
        df = df.set_index(["id"])

    # filter columns of interest
    if data == "budget":
        columns_of_interest = [
            "title",
            "school_year",
            "start_date",
            "end_date",
            "departments",
            "nb_students",
            "updated_at",
            "status",
            "validated_at",
            "is_recurring",
            "has_budget",
        ] + choices["budgets"]
        df = df[columns_of_interest]
    elif data == "data":
        columns_of_interest = [
            "title",
            "school_year",
            "start_date",
            "end_date",
            "departments",
            "members",
            "axis",
            "priority",
            "paths",
            "skills",
            "divisions",
            "mode",
            "requirement",
            "location",
            "nb_students",
            "updated_at",
            "status",
            "validated_at",
            "is_recurring",
            "has_budget",
        ] + choices["budgets"]
        df = df[columns_of_interest]

    # add budget columns for "année scolaire"
    if data in ["data", "budget"]:
        for budget in choices["budget"]:
            df[budget] = df[[budget + "_1", budget + "_2"]].sum(axis=1)

    # filter draft projects
    if not draft:
        df = df[df["status"] != "draft"]

    # filter for school year
    if sy:
        if sy == "current":
            df = df[df["school_year"].isin([sy_current, sy_next])]
        elif sy == "next":
            df = df[df["school_year"] == sy_next]
        else:
            df = df[df["school_year"] == sy]

    # replace values by labels for members field and
    # fields with choices defined as tuples
    if labels:
        if "created_by" in df.columns.tolist():
            df["created_by"] = df["created_by"].apply(lambda x: get_name(uid=x))
        df["members"] = df["members"].map(
            lambda x: ",".join([get_name(e) for e in x.split(",")])
        )
        df["axis"] = df["axis"].map(axes)
        df["priority"] = df["priority"].map(priorities)
        df["location"] = df["location"].map(lambda c: get_label(c, "location"))
        df["requirement"] = df["requirement"].map(lambda c: get_label(c, "requirement"))

    return df


def get_comments_df(id):
    """Convert ProjectComment table to DataFrame"""
    if ProjectComment.query.count() != 0:
        comments = [
            row_to_dict(c)
            for c in ProjectComment.query.filter(ProjectComment.project_id == id).all()
        ]
        for c in comments:
            c["pid"] = str(User.query.get(c["uid"]).p.id)
            del c["project_id"]
            del c["uid"]
        # set Id column as index
        df = pd.DataFrame(
            comments, columns=["id", "pid", "message", "posted_at"]
        ).set_index(["id"])
    else:
        df = pd.DataFrame(columns=["id", "pid", "message", "posted_at"])
    return df


def save_projects_df(path, projects_file):
    """Save Project table as Pickled DataFrame"""
    df = get_projects_df(data="db")

    # save Pickled dataframe
    filename = f"{projects_file}-{get_datetime():%Y%m%d_%H%M%S}.pkl"
    filepath = path / filename
    with open(filepath, "wb") as f:
        pickle.dump(df, f)


def get_comment_recipients(project):
    """Get list of recipients (pid) for project comments"""
    # get project creator
    creator = project.user.pid

    # get project members
    members = [member.pid for member in project.members]

    # get the list of users who commented on the project
    comments = ProjectComment.query.filter(ProjectComment.project == project).all()
    users = [comment.user.pid for comment in comments]

    # add users with "gestion" role and "email=ready-1" preferences
    gestionnaires = [
        personnel.id
        for personnel in Personnel.query.filter(
            Personnel.role == "gestion"
        ).all()
        if personnel.user
        and personnel.user.preferences
        and "email=ready-1" in personnel.user.preferences.split(",")
    ]

    # remove duplicates and remove current user
    recipients = set([creator] + members + users + gestionnaires)
    recipients.discard(current_user.pid)

    return list(recipients)


@main.context_processor
def utility_processor():
    def at_by(at_date, pid=None, uid=None, option="s"):
        return f"{get_date_fr(at_date)} par {get_name(pid, uid, option)}"

    def krw(v, currency=True):
        if currency:
            return f"{v:,} KRW".replace(",", " ")
        else:
            return f"{v:,}".replace(",", " ")

    def get_validation_rank(status):
        if status == "draft":
            return 0
        elif status == "ready-1":
            return 1
        elif status.startswith("validated-1"):
            return 2
        elif status == "ready":
            return 3
        elif status == "validated":
            return 4

    return dict(
        get_date_fr=get_date_fr,
        at_by=at_by,
        get_name=get_name,
        get_label=get_label,
        get_project_dates=get_project_dates,
        krw=krw,
        regex_replace=re.sub,
        regex_search=re.search,
        get_validation_rank=get_validation_rank,
        __version__=__version__,
        production_env=production_env,
        AUTHOR=AUTHOR,
        REFERENT_NUMERIQUE_EMAIL=REFERENT_NUMERIQUE_EMAIL,
        GITHUB_REPO=GITHUB_REPO,
        LFS_LOGO=LFS_LOGO,
        LFS_WEBSITE=LFS_WEBSITE,
        APP_WEBSITE=APP_WEBSITE,
        BOOMERANG_WEBSITE=BOOMERANG_WEBSITE,
    )


@main.route("/")
def index():
    if current_user.is_authenticated and (
        current_user.p.role in ["admin", "gestion", "direction"]
    ):
        return redirect(url_for("main.dashboard"))
    else:
        return render_template("index.html")


@main.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    # get database status
    auto_dashboard()
    dash = Dashboard.query.first()
    lock = dash.lock
    lock_message = dash.lock_message

    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # default to automatic school year settings
    sy_auto = True

    # get total number of projects
    n_projects = Project.query.count()

    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("main.projects"))

    form = LockForm(lock="Fermé" if lock else "Ouvert")

    form3 = SetSchoolYearForm()

    if current_user.p.role == "admin" or (
        current_user.p.role in ["gestion", "direction"] and lock != 2
    ):
        # set database status
        if form.submit.data and form.validate_on_submit():
            if form.lock.data == "Ouvert":
                lock = 0
            elif current_user.p.role == "admin":
                lock = 2
            else:
                lock = 1
            dash.lock = lock
            dash.lock_message = "La base est momentanément fermée pour maintenance de l'application. La consultation reste ouverte."
            db.session.commit()
            lock_message = dash.lock_message

        # set school year dates
        if form3.sy_submit.data and form3.validate_on_submit():
            if form3.sy_auto.data:
                sy_auto = True
                sy_start, sy_end, _ = auto_school_year()
            else:
                sy_auto = False
                sy_start = form3.sy_start.data
                sy_end = form3.sy_end.data
                auto_school_year(sy_start, sy_end)
    else:
        flash("Attention maintenance : modification impossible.", "danger")

    form3.sy_start.data = sy_start
    form3.sy_end.data = sy_end
    form3.sy_auto.data = sy_auto

    return render_template(
        "dashboard.html",
        form=form,
        form2=DownloadForm(),
        form3=form3,
        n_projects=n_projects,
        lock=lock,
        lock_message=lock_message,
        app_version=app_version,
    )


@main.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    # get database status
    auto_dashboard()
    dash = Dashboard.query.first()
    lock = dash.lock
    lock_message = dash.lock_message

    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # filter selection
    form2 = ProjectFilterForm()

    if form2.validate_on_submit():
        session["filter"] = form2.filter.data

    if "filter" not in session:  # default
        if current_user.p.role in ["gestion", "direction", "admin"]:
            session["filter"] = "LFS"
        else:
            session["filter"] = current_user.p.department

    form2.filter.data = session["filter"]

    # set dynamic school years choices
    form3 = SelectSchoolYearForm()

    df = get_projects_df()
    form3.sy.choices = sorted([s for s in set(df["school_year"])], reverse=True)
    if not form3.sy.choices:
        form3.sy.choices = [sy]
    if len(form3.sy.choices) == 1:
        schoolyears = False
    else:
        schoolyears = True
        form3.sy.choices.insert(0, "Toutes les années")

    # school year selection
    if form3.validate_on_submit():
        if form3.sy.data == "Toutes les années":
            session["sy"] = None
        else:
            session["sy"] = form3.sy.data

    if "sy" not in session:
        session["sy"] = sy

    form3.sy.data = session["sy"]

    # get projects DataFrame from Project table
    if session["filter"] in ["Mes projets", "Mes projets à valider"]:
        df = get_projects_df(current_user.p.department, sy=session["sy"])
        df = df[df.members.str.contains(f"(?:^|,){current_user.p.id}(?:,|$)")]
        if session["filter"] == "Mes projets à valider":
            df = df[(df.status == "ready-1") | (df.status == "ready")]
    elif current_user.p.role in ["gestion", "direction", "admin"]:
        if session["filter"] in ["LFS", "Projets à valider"]:
            df = get_projects_df(sy=session["sy"])
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            df = get_projects_df(session["filter"], sy=session["sy"])
    else:
        if session["filter"] in [current_user.p.department, "Projets à valider"]:
            df = get_projects_df(current_user.p.department, sy=session["sy"])
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            if session["filter"] == "LFS":
                df = get_projects_df(sy=session["sy"], draft=False)
            else:
                df = get_projects_df(session["filter"], sy=session["sy"], draft=False)
            df = df[df.status != "ready-1"]

    if current_user.p.role not in ["gestion", "direction", "admin"]:
        form2.filter.choices = choices["filter-user"]

    # set labels for axis and priority choices
    df["axis"] = df["axis"].map(axes)
    df["priority"] = df["priority"].map(priorities)

    # to-do notification
    if current_user.new_messages:
        m = len(current_user.new_messages.split(","))
    else:
        m = 0
    if current_user.p.role in ["gestion", "direction"]:
        p = len(df[(df.status == "ready") | (df.status == "ready-1")])
    else:
        p = len(
            df[
                ((df.status == "ready") | (df.status == "ready-1"))
                & df.members.str.contains(f"(?:^|,){current_user.pid}(?:,|$)")
            ]
        )

    if m or p:
        message = "Vous avez "
        message += (
            f"{m} message{'s' if m > 1 else ''} non lu{'s' if m > 1 else ''}"
            if m > 0
            else ""
        )
        message += " et " if m and p else ""
        message += (
            f"{p} projet{'s' if p > 1 else ''} non-validé{'s' if p > 1 else ''}"
            if p > 0
            else ""
        )
        message += "."
        flash(message, "info")

    return render_template(
        "projects.html",
        df=df,
        sy_start=sy_start,
        sy_end=sy_end,
        lock=lock,
        lock_message=lock_message,
        form=SelectProjectForm(),
        form2=form2,
        form3=form3,
        schoolyears=schoolyears,
    )


@main.route("/form", methods=["GET"])
@main.route("/form/<int:id>/<req>", methods=["GET"])
@login_required
def project_form(id=None, req=None):
    # get database status
    lock = Dashboard.query.first().lock
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    # check for valid request
    if id and req not in ["duplicate", "update"]:
        flash("Requête non valide sur un projet.", "danger")
        return redirect(url_for("main.projects"))

    # check access rights to project
    if id:
        project = Project.query.get(id)
        if not project:
            flash(
                f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.", "danger"
            )
            return redirect(url_for("main.projects"))
        if not any(member.pid == current_user.pid for member in project.members):
            flash("Vous ne pouvez pas modifier ou dupliquer ce projet.", "danger")
            return redirect(url_for("main.projects"))
        if project.status == "validated" and req != "duplicate":
            flash(
                "Ce projet a déjà été validé, la modification est impossible.",
                "danger",
            )
            return redirect(url_for("main.projects"))

    form = ProjectForm()

    # get project data
    if id:
        data = {}
        for f in form.data:
            if f in Project.__table__.columns.keys():
                if f in ["divisions", "paths", "skills"]:
                    data[f] = getattr(project, f).split(",")
                elif f == "is_recurring":
                    data[f] = "Oui" if getattr(project, f) else "Non"
                else:
                    data[f] = getattr(project, f)

        data["members"] = [member.pid for member in project.members]

        # duplicate project
        if req == "duplicate":
            data["id"] = None
            data["uid"] = None
            data["title"] = "(Copie de) " + project.title
            data["updated_at"] = None
            data["updated_by"] = None
            data["status"] = "draft"

        # separate date and time fields
        for s in ["start", "end"]:
            t = data[f"{s}_date"].time()
            data[f"{s}_time"] = t if t != time(0, 0) else None
        if data["end_date"] == data["start_date"]:
            data["end_date"] = None
            data["end_time"] = None

        # set school year field
        if project.start_date.date() > sy_end:
            data["school_year"] = "next"
        else:
            data["school_year"] = "current"

        # fill the form with data
        form = ProjectForm(data=data)
    else:
        form = ProjectForm(
            data={
                "departments": [current_user.p.department],
                "members": [current_user.p.id],
            }
        )

    # form : get members choices
    # list of members with departments
    form.members.choices = get_member_choices()

    # form: set school year dates for calendar
    if form.school_year.data == "current":
        form.start_date.render_kw = {
            "min": sy_start,
            "max": sy_end,
        }
    else:
        form.start_date.render_kw = {
            "min": sy_start.replace(year=sy_start.year + 1),
            "max": sy_end.replace(year=sy_end.year + 1),
        }
    form.end_date.render_kw = form.start_date.render_kw

    # form: set school year choices
    choices["school_year"] = [
        ("current", f"Actuelle ({sy_start.year} - {sy_end.year})"),
        ("next", f"Prochaine ({sy_start.year + 1} - {sy_end.year + 1})"),
    ]
    form.school_year.choices = choices["school_year"]

    # form : set dynamic status choices
    if not id or form.status.data in ["draft", "ready-1"]:
        form.status.choices = [choices["status"][i] for i in [0, 1, 3]]
    elif form.status.data == "ready":
        form.status.choices = [choices["status"][2]]
        form.status.data = "adjust"
        form.status.description = "Le projet (déjà soumis à validation) sera ajusté"
    else:
        form.status.choices = choices["status"][2:]
        form.status.data = "adjust"
        form.status.description = "Le projet sera ajusté ou soumis à validation"

    # does project has budget ?
    has_budget = project.has_budget() if id else None

    return render_template(
        "form.html",
        form=form,
        has_budget=has_budget,
        choices=choices,
        lock=lock,
    )


@main.route("/form", methods=["POST"])
@login_required
def project_form_post():
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock
    # get current school year dates
    sy_start, sy_end, sy = auto_school_year()
    # set current and next school year labels
    sy_current = sy
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    form = ProjectForm()

    # get project id
    id = form.id.data

    # check access rights to project
    if id:
        project = Project.query.get(id)
        if not any(member.pid == current_user.pid for member in project.members):
            flash("Vous ne pouvez pas modifier ce projet.", "danger")
            return redirect(url_for("main.projects"))
        if project.status == "validated":
            flash(
                "Ce projet a déjà été validé, la modification est impossible.",
                "danger",
            )
            return redirect(url_for("main.projects"))

    # form : get members choices
    form.members.choices = get_member_choices()

    if form.validate_on_submit():
        date = get_datetime()

        if id:
            # create new record history
            history_entry = ProjectHistory(
                project_id=project.id,
                updated_at=project.updated_at,
                updated_by=project.updated_by,
                status=project.status,
            )
            # update project
            setattr(project, "updated_at", date)
            setattr(project, "updated_by", current_user.id)
            # get project current status
            previous_status = project.status
            previous_members = [member.pid for member in project.members]
        else:
            # create new project
            project = Project(
                created_at=date,
                uid=current_user.id,
                updated_at=date,
                updated_by=current_user.id,
            )
            previous_status = ""
            previous_members = []

        # process form data
        for f in form.data:
            if f != "id" and f in Project.__table__.columns.keys():
                form_data = getattr(form, f).data
                if f in ["divisions", "paths", "skills"]:
                    data = ",".join(form_data)
                elif re.match(r"link_[1-4]$", f):
                    if form_data:
                        if re.match(r"^https?://", form_data):
                            data = form_data.strip()
                        else:
                            data = "https://" + form_data.strip()
                elif re.match(r"(start|end)_date", f):
                    f_t = re.sub(r"date$", "time", f)
                    form_data_t = getattr(form, f_t).data
                    if form_data and form_data_t:
                        f_start = datetime.combine(form_data, form_data_t)
                        data = f_start
                    elif not form_data:
                        data = f_start
                    else:
                        f_start = datetime.combine(form_data, datetime.min.time())
                        data = f_start
                elif f == "students":
                    if form.requirement.data == "no" and (
                        form_data or form.status.data == "ready"
                    ):
                        students = form_data.strip().splitlines()
                        # keep only non-empty lines
                        students = [line for line in students if line]
                        for i in range(len(students)):
                            student = re.split(r" *\t+ *| *, *|  +", students[i].strip())
                            if len(form.divisions.data) == 1 and len(student) == 2:
                                # tilte() student name
                                student = [student[i].strip().title() for i in range(2)]
                                # add class name
                                student.insert(0, form.divisions.data[0])
                            else:
                                # lower() class name, tilte() student name
                                student = [
                                    student[j].strip().lower()
                                    if j == 0
                                    else student[j].strip().title()
                                    for j in range(3)
                                ]
                                # format class names (6e à 1e)
                                student[0] = re.sub(
                                    r"^([1-6]) *(?:e|(?:è|e)me|de|nde|(?:è|e)re)? *([ab])$",
                                    lambda p: f"{p.group(1)}e{p.group(2).upper()}",
                                    student[0],
                                )
                                # format class name (Terminale)
                                student[0] = re.sub(
                                    r"^0e?|t(a?le|erminale)$", "Terminale", student[0]
                                )
                                # format class name (primaire sauf gs)
                                student[0] = re.sub(
                                    r"^((?:cm|ce)[12]|cp|ps/ms) *([ab])$",
                                    lambda p: f"{p.group(1)}{p.group(2).upper()}",
                                    student[0],
                                )

                            students[i] = tuple(student)

                        # sort by student name, then by class
                        students.sort(
                            key=lambda x: (choices["divisions"].index(x[0]), x[1])
                        )
                        students = "\r\n".join(
                            f"{x[0]}, {x[1]}, {x[2]}" for x in students
                        )
                        data = students
                elif f == "school_year":
                    data = sy_current if form_data == "current" else sy_next
                elif f in ["fieldtrip_ext_people", "fieldtrip_impact"]:
                    if re.match(r"(?ai)aucun|non|sans objet", form_data):
                        data = ""
                    else:
                        data = form_data.strip()
                elif f == "is_recurring":
                    data = True if form_data == "Oui" else False
                elif f == "status":
                    data = previous_status if form_data == "adjust" else form_data
                else:
                    if isinstance(form_data, str):
                        data = form_data.strip()
                    else:
                        data = form_data

                if id and f in ProjectHistory.__table__.columns.keys():
                    # check if field has changed
                    if getattr(project, f) != data:
                        setattr(history_entry, f, getattr(project, f))

                setattr(project, f, data)

        # set axis data
        setattr(project, "axis", form.priority.data[:2])

        # set project departments
        departments = {
            Personnel.query.get(int(id)).department for id in form.members.data
        }
        setattr(project, "departments", ",".join(departments))

        # check students list consistency with nb_students and divisions fields
        if project.requirement == "no" and (
            project.students or project.status == "ready"
        ):
            students = project.students.splitlines()
            nb_students = len(students)
            divisions = ",".join(
                sorted(
                    {student.split(", ")[0] for student in students},
                    key=choices["divisions"].index,
                )
            )
            if nb_students != project.nb_students:
                setattr(project, "nb_students", nb_students)
            if divisions != project.divisions:
                setattr(project, "divisions", divisions)

        # remove useless inputs
        if project.requirement == "yes":
            setattr(project, "students", None)
        if project.location != "outer":
            setattr(project, "fieldtrip_address", None)
            setattr(project, "fieldtrip_ext_people", None)
            setattr(project, "fieldtrip_impact", None)

        # clean "invisible" budgets
        if form.school_year.data == "current":
            if project.start_date.year == sy_end.year:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_1", 0)
                    setattr(project, "budget_" + budget + "_c_1", None)
            if project.end_date.year == sy_start.year:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_2", 0)
                    setattr(project, "budget_" + budget + "_c_2", None)
        else:
            if project.start_date.year == sy_end.year + 1:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_1", 0)
                    setattr(project, "budget_" + budget + "_c_1", None)
            if project.end_date.year == sy_start.year + 1:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_2", 0)
                    setattr(project, "budget_" + budget + "_c_2", None)

        for year in ["1", "2"]:
            for budget in ["hse", "exp", "trip", "int"]:
                if getattr(form, "budget_" + budget + "_" + year).data == 0:
                    setattr(project, "budget_" + budget + "_c_" + year, None)

        # add project and project history
        if id:
            # add new history entry
            db.session.add(history_entry)
            db.session.flush()
        else:
            # add new project
            db.session.add(project)
            db.session.flush()

        # update project members
        members = [int(m) for m in form.members.data]
        if set(previous_members) != set(members):
            if id:  # clear existing members
                ProjectMember.query.filter_by(project_id=id).delete()
                db.session.flush()
            # add new members
            for pid in members:
                project_member = ProjectMember(project_id=project.id, pid=pid)
                db.session.add(project_member)

        # update database
        db.session.commit()

        # flash and log information
        if id:
            flash(f'Le projet "{project.title}" a été modifié avec succès !', "info")
            logger.info(f"Project id={id} modified by {current_user.p.email}")
        else:
            flash(f'Le projet "{project.title}" a été créé avec succès !', "info")
            logger.info(f"New project added ({project.title}) by {current_user.p.email}")

        # save pickle when a new project is added
        if not id:
            save_projects_df(data_path, projects_file)

        # send email notification if status=ready-1 or status=ready
        if project.status.startswith("ready") and not previous_status.startswith("ready"):
            if gmail_service:
                error = send_notification(project.status, project)
                if error:
                    flash(error, "warning")
            else:
                flash(
                    "Attention : aucune notification n'est envoyée par e-mail (API GMail non connectée).",
                    "warning",
                )

        return redirect(url_for("main.projects"))

    # form: set school year dates for calendar
    if form.school_year.data == "current":
        form.start_date.render_kw = {
            "min": sy_start,
            "max": sy_end,
        }
    else:
        form.start_date.render_kw = {
            "min": sy_start.replace(year=sy_start.year + 1),
            "max": sy_end.replace(year=sy_end.year + 1),
        }
    form.end_date.render_kw = form.start_date.render_kw

    # form: set school year choices
    choices["school_year"] = [
        ("current", f"Actuelle ({sy_start.year} - {sy_end.year})"),
        ("next", f"Prochaine ({sy_start.year + 1} - {sy_end.year + 1})"),
    ]
    form.school_year.choices = choices["school_year"]

    # form : set dynamic status choices
    if not id or project.status in ["draft", "ready-1"]:
        form.status.choices = [choices["status"][i] for i in [0, 1, 3]]
    elif project.status == "ready":
        form.status.choices = [choices["status"][2]]
        form.status.data = "adjust"
        form.status.description = "Le projet (déjà soumis à validation) sera ajusté"
    else:
        form.status.choices = choices["status"][2:]
        form.status.data = "adjust"
        form.status.description = "Le projet sera ajusté ou soumis à validation"

    # does project has budget ?
    has_budget = (
        project.has_budget()
        if id
        else sum(
            [
                getattr(form, f).data or 0
                for f in form.data
                if re.match(r"^budget_(hse|exp|trip|int)_[12]$", f)
            ]
        )
    )

    return render_template(
        "form.html",
        form=form,
        has_budget=has_budget,
        choices=choices,
        lock=lock,
    )


@main.route("/project/validation/<int:id>", methods=["GET"])
@login_required
def validate_project(id):
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    project = Project.query.get(id)
    if (
        not project
        or current_user.p.role != "direction"
        or project.status not in ["ready-1", "ready"]
    ):
        return redirect(url_for("main.projects"))

    # add new record history
    history_entry = ProjectHistory(
        project_id=project.id,
        updated_at=project.updated_at,
        updated_by=project.updated_by,
        status=project.status,
    )
    db.session.add(history_entry)

    # update project
    date = get_datetime()
    project.updated_at = date
    project.updated_by = current_user.id

    if project.status == "ready-1":
        project.status = "validated-1"
    elif project.status == "ready":
        project.status = "validated"

    # update database
    db.session.commit()
    # save_projects_df(data_path, projects_file)

    message = f'Le projet "{project.title}" '
    if project.status == "validated-1":
        if project.has_budget():
            message += "et son budget ont été approuvés"
        else:
            message += "a été approuvé"
    else:
        message += "a été validé"
    message += " avec succès."
    flash(message, "info")

    # send email notification
    if gmail_service:
        error = send_notification(project.status, project)
        if error:
            flash(error, "warning")
    else:
        flash(
            "Attention : aucune notification n'est envoyée par e-mail (API GMail non connectée).",
            "warning",
        )

    logger.info(f"Project id={id} ({project.title}) validated by {current_user.p.email}")

    return redirect(url_for("main.projects"))


@main.route("/project/devalidation/<int:id>", methods=["GET"])
@login_required
def devalidate_project(id):
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    project = Project.query.get(id)
    if not project or current_user.p.role != "direction" or project.status != "validated":
        return redirect(url_for("main.projects"))

    # add new record history
    history_entry = ProjectHistory(
        project_id=project.id,
        updated_at=project.updated_at,
        updated_by=project.updated_by,
        status=project.status,
    )
    db.session.add(history_entry)

    # update project
    date = get_datetime()
    project.updated_at = date
    project.updated_by = current_user.id

    if project.status == "validated":
        project.status = "validated-10"

    # update database
    db.session.commit()
    # save_projects_df(data_path, projects_file)

    flash(f'Le projet "{project.title}" a été dévalidé avec succès.', "info")

    # send email notification
    if gmail_service:
        error = send_notification(project.status, project)
        if error:
            flash(error, "warning")
    else:
        flash(
            "Attention : aucune notification n'est envoyée par e-mail (API GMail non connectée).",
            "warning",
        )

    logger.info(
        f"Project id={id} ({project.title}) devalidated by {current_user.p.email}"
    )

    return redirect(url_for("main.projects"))


@main.route("/project/delete/<int:id>", methods=["GET"])
@login_required
def delete_project(id):
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    project = Project.query.get(id)
    if project:
        if current_user.id == project.uid and project.status != "validated":
            title = project.title
            try:
                db.session.delete(project)
                db.session.commit()
                # save_projects_df(data_path, projects_file)
                flash(f'Le projet "{title}" a été supprimé avec succès.', "info")
                logger.info(
                    f"Project id={id} ({title}) deleted by {current_user.p.email}"
                )
            except Exception as e:
                db.session.rollback()  # rollback in case of error
                logger.info(
                    f"Error deleting project id={id} ({title}) by {current_user.p.email}. Error: {e}"
                )
                flash(f'Erreur : suppression impossible projet "{title}."', "danger")
        else:
            flash("Vous ne pouvez pas supprimer ce projet.", "danger")
    else:
        flash(f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.", "danger")

    return redirect(url_for("main.projects"))


# fiche projet avec commentaires
@main.route("/project/<int:id>", methods=["GET"])
@login_required
def project(id):
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    project = Project.query.get(id)

    if project:
        if (
            any(member.pid == current_user.pid for member in project.members)
            or current_user.p.role in ["gestion", "direction"]
            or project.status not in ["draft", "ready-1"]
        ):
            # update user : remove new comment badge for this project
            if current_user.new_messages:
                new_messages = ",".join(
                    [i for i in current_user.new_messages.split(",") if i != str(id)]
                )
                current_user.new_messages = new_messages
                # update database
                db.session.commit()

            # get project data as DataFrame
            df = get_projects_df(filter=id)

            # set axes and priorities labels
            df["axis"] = df["axis"].map(axes)
            df["priority"] = df["priority"].map(priorities)

            # get project row as named tuple
            p = next(df.itertuples())

            # get comments on project as DataFrame
            dfc = get_comments_df(id)

            # get e-mail notification recipients
            recipients = get_comment_recipients(project)

            if recipients:
                form = CommentForm(project=id, recipients=",".join([str(pid) for pid in recipients]))
                for i, recipient in enumerate(recipients):
                    form.message.description += get_name(recipient)
                    if i < len(recipients) - 2:
                        form.message.description += ", "
                    elif i == len(recipients) - 2:
                        form.message.description += " et "
                    else:
                        form.message.description += "."
            else:
                form = CommentForm(project=id, recipients=None)
                form.message.description += "personne (aucun destinataire trouvé)."

            return render_template(
                "project.html",
                project=p,
                dfc=dfc,
                sy_start=sy_start,
                sy_end=sy_end,
                form=form,
                lock=lock,
            )
        else:
            flash("Vous ne pouvez pas accéder à cette fiche projet.", "danger")
    else:
        flash(f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.", "danger")

    return redirect(url_for("main.projects"))


# historique du projet
@main.route("/history/<int:project_id>", methods=["GET"])
@login_required
def history(project_id):
    project = Project.query.get(project_id)
    if project:
        if any(
            member.pid == current_user.pid for member in project.members
        ) or current_user.p.role in [
            "gestion",
            "direction",
        ]:
            # create a list of triplets (status, updated_at, updated_by)
            project_history = [
                (project.status, project.updated_at, project.updated_by)
            ] + [
                (entry.status, entry.updated_at, entry.updated_by)
                for entry in project.history
            ]

            if current_user.p.role in ["gestion", "direction"]:
                # remove all draft modification events
                while len(project_history) > 1 and project_history[-2][0] == "draft":
                    del project_history[-2]

            # create html block
            history_html = render_template(
                "_history_modal.html",
                project_history=project_history,
                has_budget=project.has_budget(),
            )
            return jsonify({"html": history_html})
        return jsonify(
            {"Erreur": "Vous ne pouvez pas accéder à l'historique projet."}
        ), 404
    else:
        return jsonify(
            {
                "Erreur": f"Le projet demandé (id = {project_id}) n'existe pas ou a été supprimé."
            }
        ), 404


@main.route("/project/comment/add", methods=["POST"])
@login_required
def project_add_comment():
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock == 2:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    form = CommentForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)

        # add comment
        # only if user is a project member or has "gestion" or "direction" role
        if any(
            member.pid == current_user.pid for member in project.members
        ) or current_user.p.role in [
            "gestion",
            "direction",
        ]:
            # add new comment
            date = get_datetime()
            comment = ProjectComment(
                message=form.message.data,
                posted_at=date,
                project_id=project.id,
                uid=current_user.id,
            )
            db.session.add(comment)
            db.session.flush()

            # e-mail notification recipients
            if form.recipients.data:
                recipients = form.recipients.data.split(",")
                # update user table: set new_message notification
                for pid in recipients:
                    user = Personnel.query.get(pid).user
                    if user:
                        if user.new_messages:
                            user.new_messages += f",{str(project.id)}"
                        else:
                            user.new_messages = str(project.id)
                        db.session.flush()

                # send email notification
                if gmail_service:
                    error = send_notification(
                        "comment", project, recipients, form.message.data
                    )
                    if error:
                        flash(error, "warning")
                    else:
                        flash("Notification envoyée par e-mail avec succès !", "info")
                        logger.info(f"New comment on project id={project.id} sent by {current_user.p.email}.")
                else:
                    flash(
                        "Attention : aucune notification n'est envoyée par e-mail (API GMail non connectée).",
                        "warning",
                    )
            else:
                flash(
                    "Attention : aucune notification n'a pu être envoyée par e-mail (aucun destinataire trouvé).",
                    "warning",
                )

            # update database
            db.session.commit()
            # save_projects_df(data_path, projects_file)

            return redirect(url_for("main.project", id=id))
        else:
            flash("Vous ne pouvez pas commenter ce projet.", "danger")

    return redirect(url_for("main.projects"))


@main.route("/project/print", methods=["POST"])
@login_required
def print_fieldtrip_pdf():
    form = SelectProjectForm()

    if not matplotlib_module:
        flash(
            "Ressources serveur insuffisantes pour générer la fiche de sortie scolaire.",
            "danger",
        )
        return redirect(url_for("main.projects"))

    if form.validate_on_submit():
        # get project id
        id = form.project.data
        project = Project.query.get(id)

        if any(
            member.pid == current_user.pid for member in project.members
        ) or current_user.p.role in [
            "gestion",
            "direction",
            "admin",
        ]:
            # data
            data = [
                ["Titre du projet", project.title],
                ["Date", get_date_fr(project.start_date)],
                ["Horaire de départ", get_date_fr(project.start_date, withdate=False)],
                ["Horaire de retour", get_date_fr(project.end_date, withdate=False)],
                ["Classes", project.divisions.replace(",", ", ")],
                ["Nombre d'élèves", str(project.nb_students)],
                [
                    "Encadrement (personnels LFS)",
                    ", ".join([get_name(member.pid) for member in project.members]),
                ],
                [
                    "Encadrement (personnes extérieures)",
                    project.fieldtrip_ext_people if project.fieldtrip_ext_people else "/",
                ],
                ["Lieu et adresse", project.fieldtrip_address.replace("\r", "")],
                [
                    "Incidence sur les autres cours et AES",
                    project.fieldtrip_impact.replace("\r", "")
                    if project.fieldtrip_impact != ""
                    else "/",
                ],
                [
                    "Sortie scolaire validée \npar le chef d'établissement",
                    get_date_fr(project.updated_at),
                ],
                [
                    f"Transmis à l'Ambassade de France \n{AMBASSADE_EMAIL}",
                    get_date_fr(get_datetime()),
                ],
            ]

            if current_user.p.role not in ["gestion", "direction", "admin"]:
                data[-1] = [
                    "Transmis à l'Ambassade de France \npar l'agent gestionnaire",
                    "Date de la transmission",
                ]

            filename = fieldtrip_pdf.replace("<id>", str(id))
            filepath = data_path / filename
            generate_fieldtrip_pdf(data, data_path, filepath)

            return send_file(filepath, as_attachment=False)

    return redirect(url_for("main.projects"))


@main.route("/data", methods=["GET", "POST"])
@login_required
def data():
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # personnel list
    choices["personnels"] = sorted(
        [
            (
                personnel.id,
                f"{personnel.name} {personnel.firstname}",
                personnel.department,
            )
            for personnel in Personnel.query.all()
        ],
        key=lambda x: x[1],
    )

    # convert Project table to DataFrame
    df = get_projects_df(draft=False, data="data")

    # calculate the distribution of projects (number and pecentage)
    dist = {}

    # total number of projects
    dist["TOTAL"] = len(df)
    N = dist["TOTAL"]

    for axis in choices["axes"]:
        n = len(df[df.axis == axis[0]])
        s = sum(df[df.axis == axis[0]]["nb_students"])
        dist[axis[0]] = (n, f"{N and n / N * 100 or 0:.0f}%")  # 0 if division by zero
        for priority in choices["priorities"][choices["axes"].index(axis)]:
            p = len(df[df.priority == priority[0]])
            dist[priority[0]] = (p, f"{n and p / n * 100 or 0:.0f}%", s)

    for department in choices["departments"]:
        d = len(df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")])
        s = sum(
            df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")]["nb_students"]
        )
        dist[department] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    d = len(df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)])
    if len(df) != 0:
        s = sum(
            df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)][
                "nb_students"
            ]
        )
    else:
        s = 0
    dist["secondary"] = (d, f"{N and d / N * 100 or 0:.0f}%", s)
    dist["primary"] = dist["Primaire"]
    dist["kindergarten"] = dist["Maternelle"]

    for member in choices["personnels"]:
        d = len(df[df.members.str.contains(f"(?:^|,){member[0]}(?:,|$)")])
        s = sum(df[df.members.str.contains(f"(?:^|,){member[0]}(?:,|$)")]["nb_students"])
        dist[member[0]] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    choices["paths"] = ProjectForm().paths.choices
    for path in choices["paths"]:
        d = len(df[df.paths.str.contains(path)])
        s = sum(df[df.paths.str.contains(path)]["nb_students"])
        dist[path] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    choices["skills"] = ProjectForm().skills.choices
    for skill in choices["skills"]:
        d = len(df[df.skills.str.contains(skill)])
        s = sum(df[df.skills.str.contains(skill)]["nb_students"])
        dist[skill] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    for section in ["secondaire", "primaire", "maternelle"]:
        dist[section] = len(
            df[~df.divisions.str.split(",").map(set(choices[section]).isdisjoint)]
        )
        n = dist[section]
        for division in choices[section]:
            d = len(df[df.divisions.str.contains(division)])
            dist[division] = (d, f"{n and d / n * 100 or 0:.0f}%")

    choices["mode"] = ProjectForm().mode.choices
    for m in choices["mode"]:
        d = len(df[df["mode"] == m])
        s = sum(df[df["mode"] == m]["nb_students"])
        dist[m] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    choices["requirement"] = ProjectForm().requirement.choices
    for r in choices["requirement"]:
        d = len(df[df.requirement == r[0]])
        s = sum(df[df.requirement == r[0]]["nb_students"])
        dist[r[0]] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    choices["location"] = ProjectForm().location.choices
    for loc in choices["location"]:
        d = len(df[df.location == loc[0]])
        s = sum(df[df.location == loc[0]]["nb_students"])
        dist[loc[0]] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    # budget

    # data for graphs
    # axes et priorités du projet d'établissement
    dfa = pd.DataFrame(
        {
            "priority": [
                p[1] for axis in choices["priorities"] for p in axis if dist[p[0]][0] != 0
            ],
            "axis": [
                choices["axes"][i][1]
                for i, axis in enumerate(choices["priorities"])
                for p in axis
                if dist[p[0]][0] != 0
            ],
            "project": [
                dist[p[0]][0]
                for axis in choices["priorities"]
                for p in axis
                if dist[p[0]][0] != 0
            ],
        }
    )

    # sunburst chart
    # axes et priorités du projet d'établissement
    graph_html = (
        sunburst_chart(dfa) if graph_module else "Ressources serveur insuffisantes."
    )

    # stacked bar chart
    # axes et priorités du projet d'établissement
    graph_html2 = (
        bar_chart(dfa, choices) if graph_module else "Ressources serveur insuffisantes."
    )

    # data for
    # stacked bar chart as a timeline
    # stop month for range
    sy_end_month = sy_end.month + 12 if sy_end.year == sy_start.year + 1 else sy_end.month
    # months (numbers) of the school year
    syi = [m % 12 for m in range(sy_start.month, sy_end_month + 1)]
    syi = [12 if m == 0 else m for m in syi]
    # months (French names) of the school year
    sy_months = [
        format_date(datetime(1900, m, 1), format="MMMM", locale="fr_FR").capitalize()
        for m in syi
    ]

    dft = pd.DataFrame({f"Année scolaire {sy_start.year}-{sy_end.year}": sy_months})

    for project in df.itertuples():
        y = sy_start.year
        timeline = [0] * len(sy_months)
        for i, m in enumerate(syi):
            if m == 1:
                y += 1
            if project.start_date < datetime(
                y, m, calendar.monthrange(y, m)[1]
            ) and project.end_date > datetime(y, m, 1):
                timeline[i] = 1
        dft[
            project.title
            + f"<br>{get_project_dates(project.start_date, project.end_date)}"
            + f"<br>{project.divisions}"
        ] = timeline

    # drop July and August if no projects
    dft = dft[~((dft.iloc[:, 0] == "Juillet") & (dft.iloc[:, 1:].sum(axis=1) == 0))]
    dft = dft[~((dft.iloc[:, 0] == "Août") & (dft.iloc[:, 1:].sum(axis=1) == 0))]

    # stacked bar chart as a timeline
    graph_html3 = (
        timeline_chart(dft) if graph_module else "Ressources serveur insuffisantes."
    )

    return render_template(
        "data.html",
        choices=choices,
        df=df,
        dist=dist,
        graph_html=graph_html,
        graph_html2=graph_html2,
        graph_html3=graph_html3,
    )


@main.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    # get school year
    sy_start, sy_end, sy = auto_school_year()
    # set current and next school year labels
    sy_current = sy
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    # check for authorized user
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("main.projects"))

    ### school year tab ###
    form = SelectSchoolYearForm()

    # set dynamic school years choices
    df = get_projects_df(draft=False, data="budget")
    form.sy.choices = sorted([(s, s) for s in set(df["school_year"])], reverse=True)
    if not form.sy.choices:
        form.sy.choices = [(sy_current, sy_current)]

    if (sy_next, sy_next) in form.sy.choices:
        form.sy.choices.insert(1, ("recurring", "Projets récurrents"))
    else:
        form.sy.choices.insert(0, ("recurring", "Projets récurrents"))

    ## get form POST data
    if form.validate_on_submit():
        sy = form.sy.data
    else:
        sy = sy_current

    # set form default data
    form.sy.data = sy

    ## filter DataFrame
    if sy == "recurring":
        dfs = df[(df["school_year"] == sy_current) & (df["is_recurring"] == "Oui")]
    else:
        dfs = df[df["school_year"] == sy]

    # recurring school year
    if sy == "recurring":
        sy = "Année n - Année n+1"

    ### fiscal year tab ###
    form2 = SelectFiscalYearForm()

    # set dynamic fiscal years choices
    form2.fy.choices = sorted(
        [
            y
            for y in set(
                df["school_year"]
                .str.split(" - ", expand=True)
                .drop_duplicates()
                .values.flatten()
            )
        ],
        reverse=True,
    )
    if not form2.fy.choices:
        form2.fy.choices = [str(sy_end.year), str(sy_start.year)]

    ## get form2 POST data
    if form2.validate_on_submit():
        fy = form2.fy.data
        tabf = True
    else:
        fy = (
            str(sy_start.year)
            if sy_start.year == datetime.now().year
            else str(sy_end.year)
        )
        tabf = False

    # set form default data
    form2.fy.data = fy

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


@main.route("/data/personnels", methods=["GET", "POST"])
@login_required
def data_personnels():
    if current_user.p.role in ["gestion", "direction", "admin"]:
        personnels = Personnel.query.order_by(
            case(
                {role: index for index, role in enumerate(choices["role"])},
                value=Personnel.role,
                else_=len(choices["role"]),  # this will place empty roles at the end
            ),
            Personnel.name,
        ).all()

        return render_template(
            "personnels.html",
            personnels=personnels,
            choices=choices,
        )
    else:
        return redirect(url_for("main.projects"))


@main.route("/download", methods=["POST"])
@login_required
def download():
    form = DownloadForm()
    if form.validate_on_submit():
        if current_user.p.role in ["gestion", "direction", "admin"]:
            df = get_projects_df(data="Excel", labels=True)
            if not df.empty:
                date = get_datetime().strftime("%Y-%m-%d-%Hh%M")
                filename = f"Projets_LFS-{date}.xlsx"
                filepath = data_path / filename
                df.to_excel(
                    filepath,
                    sheet_name="Projets pédagogiques LFS",
                    columns=df.columns,
                )
                return send_file(filepath, as_attachment=True)

    return Response(status=HTTPStatus.NO_CONTENT)


@main.route("/language/<language>")
def set_language(language="fr"):
    response = make_response(redirect(request.referrer or "/"))
    response.set_cookie("lang", language)
    return response
