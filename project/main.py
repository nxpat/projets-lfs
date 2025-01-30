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
)

from flask_login import login_required, current_user

from sqlalchemy import case

from http import HTTPStatus

from .models import Personnel, Project, Comment, Dashboard, User
from . import db

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

from datetime import datetime, time
from zoneinfo import ZoneInfo
from babel.dates import format_date, format_datetime

from pathlib import PurePath
import os

import pandas as pd
import pickle
import re

import logging

from . import app_version, data_path

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
BOOMERANG_WEBSITE = os.getenv("BOOMERANG_WEBSITE")

# init logger
logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# data directory
data_dir = "data"

# basefilename to save projects data (pickle format)
projects_file = "projets"

# field trip PDF form filename
fieldtrip_pdf = "formulaire_sortie-<id>.pdf"


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_date_fr(date, withdate=True, withtime=False):
    if not date or str(date) == "NaT":
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


def auto_school_year():
    today = get_datetime()

    sy_start = datetime(today.year - 1 if today.month < 9 else today.year, 9, 1)
    sy_end = datetime(today.year if today.month < 9 else today.year + 1, 8, 31)

    return sy_start, sy_end


def get_name(email, option=None):
    personnel = Personnel.query.filter_by(email=email).first()
    if option == "nf":
        return f"{personnel.name} {personnel.firstname}"
    elif option == "f":
        return f"{personnel.firstname}"
    elif option == "n":
        return f"{personnel.name}"
    else:
        return f"{personnel.firstname} {personnel.name}"


def get_names(emails, option=None):
    return re.sub(
        r"([^,]+)",
        lambda match: get_name(match.group(1), option),
        emails,
    ).replace(",", ", ")


def get_label(choice, field):
    """get the label for the field choice"""
    if field == "location":
        return next(iter([x[1] for x in ProjectForm().location.choices if x[0] == choice]))
    elif field == "requirement":
        return next(iter([x[1] for x in ProjectForm().requirement.choices if x[0] == choice]))
    else:
        return None


def get_teacher_choices():
    return {
        department: sorted(
            [
                (personnel.email, f"{personnel.firstname} {personnel.name}")
                for personnel in Personnel.query.filter(Personnel.department == department)
                # .filter(Personnel.role.is_(None) | (Personnel.role != "admin"))
                .all()
            ],
            key=lambda x: x[1],
        )
        for department in choices["departments"]
        if Personnel.query.filter(Personnel.department == department).all()
    }


def get_projects_df(filter=None, sy=None, draft=True, data=None, labels=False):
    """Convert Project table to DataFrame"""
    # get application dashboard
    dash = Dashboard.query.get(1)
    # get current school year dates
    sy_start, sy_end = dash.sy_start, dash.sy_end
    # set current and next school year labels
    sy_current = f"{sy_start.year} - {sy_end.year}"
    sy_next = f"{sy_start.year+1} - {sy_end.year+1}"

    # SQLAlchemy ORM query
    if isinstance(filter, str):
        projects = [
            p.__dict__
            for p in Project.query.filter(
                Project.departments.contains(f"(^|,){filter}(,|$)")
            ).all()
        ]
    elif isinstance(filter, int):
        projects = [Project.query.get(filter).__dict__]
    else:
        projects = [p.__dict__ for p in Project.query.all()]

    # add and remove fields
    for p in projects:
        if data != "db":
            p["email"] = User.query.get(p["user_id"]).p.email
            p.pop("user_id", None)
        if data == "Excel":
            p.pop("nb_comments", None)
        if data not in ["db", "Excel"]:
            p["has_budget"] = Project.query.get(p["id"]).has_budget()
        p.pop("_sa_instance_state", None)

    # set columns for DataFrame
    columns = Project.__table__.columns.keys()
    if data != "db":
        columns.remove("user_id")
        columns.insert(1, "email")
    if data == "Excel":
        columns.remove("nb_comments")
    if data not in ["db", "Excel"]:
        columns.append("has_budget")

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
            "teachers",
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
        else:
            df = df[df["school_year"] == sy]

    # replace values by labels for teachers field and
    # fields with choices defined as tuples
    if labels:
        df["teachers"] = df["teachers"].map(
            lambda x: ",".join([get_name(e) for e in x.split(",")])
        )
        df["axis"] = df["axis"].map(axes)
        df["priority"] = df["priority"].map(priorities)
        df["location"] = df["location"].map(lambda c: get_label(c, "location"))
        df["requirement"] = df["requirement"].map(lambda c: get_label(c, "requirement"))

    return df


def get_comments_df(id):
    """Convert Comment table to DataFrame"""
    if Comment.query.count() != 0:
        comments = [c.__dict__ for c in Comment.query.filter(Comment.project_id == id).all()]
        for c in comments:
            c.pop("_sa_instance_state", None)
            c["email"] = User.query.get(c["user_id"]).p.email
            c.pop("project_id", None)
            c.pop("user_id", None)
        # set Id column as index
        df = pd.DataFrame(comments, columns=["id", "email", "message", "posted_at"]).set_index(
            ["id"]
        )
    else:
        df = pd.DataFrame(columns=["id", "email", "message", "posted_at"])
    return df


def save_projects_df(path, projects_file):
    """Save Project table as Pickled DataFrame"""
    df = get_projects_df(data="db")

    # save Pickled dataframe
    filename = f"{projects_file}-{get_datetime():%Y%m%d_%H%M%S}.pkl"
    filepath = os.fspath(PurePath(path, data_dir, filename))
    with open(filepath, "wb") as f:
        pickle.dump(df, f)


@main.context_processor
def utility_processor():
    def get_created_at(date, user_email, project_email):
        if user_email == project_email:
            return f"{get_date_fr(date)} par moi"
        else:
            return f"{get_date_fr(date)} par {get_name(project_email)}"

    def krw(v, currency=True):
        if currency:
            return f"{v:,} KRW".replace(",", " ")
        else:
            return f"{v:,}".replace(",", " ")

    def regex_replace(pattern, repl, string, count=0, flags=0):
        return re.sub(pattern, repl, string, count, flags)

    def get_validation_rank(status):
        if status == "draft":
            return 0
        elif status == "ready-1":
            return 1
        elif status == "validated-1":
            return 2
        elif status == "ready":
            return 3
        elif status == "validated":
            return 4

    return dict(
        get_date_fr=get_date_fr,
        get_created_at=get_created_at,
        get_name=get_name,
        get_label=get_label,
        get_project_dates=get_project_dates,
        krw=krw,
        regex_replace=regex_replace,
        get_validation_rank=get_validation_rank,
        AUTHOR=AUTHOR,
        REFERENT_NUMERIQUE_EMAIL=REFERENT_NUMERIQUE_EMAIL,
        GITHUB_REPO=GITHUB_REPO,
        LFS_LOGO=LFS_LOGO,
        LFS_WEBSITE=LFS_WEBSITE,
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
    dash = Dashboard.query.get(1)
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end = dash.sy_start, dash.sy_end
    sy_auto = dash.sy_auto

    n_projects = Project.query.count()

    form = LockForm(lock="Fermé" if lock else "Ouvert")
    form3 = SetSchoolYearForm(sy_start=sy_start, sy_end=sy_end, sy_auto=sy_auto)

    # set database status
    if form.validate_on_submit():
        setattr(
            Dashboard.query.get(1),
            "lock",
            False if form.lock.data == "Ouvert" else True,
        )
        db.session.commit()
        lock = Dashboard.query.get(1).lock
        return redirect(url_for("main.dashboard"))

    return render_template(
        "dashboard.html",
        form=form,
        form2=DownloadForm(),
        form3=form3,
        n_projects=n_projects,
        lock=lock,
        app_version=app_version,
    )


@main.route("/schoolyear", methods=["POST"])
@login_required
def schoolyear():
    form3 = SetSchoolYearForm()

    # set school year dates
    if form3.validate_on_submit():
        dash = Dashboard.query.get(1)
        sy_auto = form3.data["sy_auto"]
        if sy_auto:
            sy_start, sy_end = auto_school_year()
        else:
            sy_start = form3.data["sy_start"]
            sy_end = form3.data["sy_end"]
        setattr(dash, "sy_auto", sy_auto)
        setattr(dash, "sy_start", sy_start)
        setattr(dash, "sy_end", sy_end)
        db.session.commit()
        return redirect(url_for("main.dashboard"))


@main.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    # create default record if Dashboard is empty
    if not Dashboard.query.first():
        # calculate default school year dates
        sy_start, sy_end = auto_school_year()
        # set default database lock to opened
        dash = Dashboard(lock=False, sy_start=sy_start, sy_end=sy_end, sy_auto=True)
        db.session.add(dash)
        db.session.commit()

    dash = Dashboard.query.get(1)
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end = dash.sy_start, dash.sy_end

    if "project" in session:
        session.pop("project")

    form2 = ProjectFilterForm()

    if form2.validate_on_submit():
        if current_user.p.role in ["gestion", "direction", "admin"]:
            session["filter"] = form2.filter.data

    # convert Project table to DataFrame
    # according to user role
    if current_user.p.role in ["gestion", "direction", "admin"]:
        if "filter" not in session:
            session["filter"] = "LFS"  # default
        if session["filter"] in ["LFS", "Projets à valider"]:
            df = get_projects_df()
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            df = get_projects_df(session["filter"])
    else:
        session["filter"] = current_user.p.department
        df = get_projects_df(session["filter"])

    form2 = ProjectFilterForm(data={"filter": session["filter"]})

    # set labels for axis and priority choices
    df["axis"] = df["axis"].map(axes)
    df["priority"] = df["priority"].map(priorities)

    # to-do notification
    new = "n" if current_user.p.role in ["gestion", "direction"] else "N"
    m = len(df[df.nb_comments.str.contains(new)])
    p = len(df[(df.status == "ready") | (df.status == "ready-1")])
    if m or p:
        message = "Vous avez "
        message += f"{m} message{'s' if m > 1 else ''}" if m > 0 else ""
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
        form=SelectProjectForm(),
        form2=form2,
    )


@main.route("/form", methods=["GET"])
@login_required
def project_form():
    dash = Dashboard.query.get(1)
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end = dash.sy_start, dash.sy_end

    # check authorizations
    if not lock:
        if "project" in session:
            id = session["project"]
        else:
            id = None
        if id:
            project = Project.query.get(id)
            if current_user.p.email not in project.teachers and current_user.p.role != "admin":
                flash("Vous ne pouvez pas modifier ce projet.", "danger")
                return redirect(url_for("main.projects"))
            elif project.status == "validated":
                flash(
                    "Ce projet a déjà été validé, la modification est impossible.",
                    "danger",
                )
                return redirect(url_for("main.projects"))
    else:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    form = ProjectForm()

    if id:
        data = {}
        for f in form.data:
            if f in Project.__table__.columns.keys():
                if f in ["departments", "teachers", "divisions", "paths", "skills"]:
                    data[f] = getattr(project, f).split(",")
                elif f == "students":
                    if project.requirement == "no" and project.students:
                        # get the width of the first two columns of the students list
                        a = getattr(project, f).split(",")
                        w1 = max(len(c) for c in [a[i] for i in range(0, len(a), 3)]) + 2
                        w2 = max(len(n) for n in [a[i] for i in range(1, len(a), 3)]) + 2
                        # print the students list table
                        tab = "\t"
                        data[f] = "\n".join(
                            f"{a[i]}{tab*((w1-len(a[i]))//4+1)}{a[i+1]}"
                            f"{tab*((w2-len(a[i+1]))//4+1)}{a[i+2]}"
                            for i in range(0, len(a), 3)
                        )
                else:
                    data[f] = getattr(project, f)

        for s in ["start", "end"]:
            t = data[f"{s}_date"].time()
            data[f"{s}_time"] = t if t != time(0, 0) else None
        if data["end_date"] == data["start_date"]:
            data["end_date"] = None
            data["end_time"] = None

        if project.start_date > sy_end:
            data["school_year"] = "next"
        else:
            data["school_year"] = "current"

        form = ProjectForm(data=data)
    else:
        form = ProjectForm(
            data={
                "departments": [current_user.p.department],
                "teachers": [current_user.p.email],
            }
        )

    # get teachers choices for ProjectForm
    form.teachers.choices = get_teacher_choices()

    # form: set school year dates for calendar
    if form.school_year.data == "current":
        form.start_date.render_kw = {
            "min": sy_start.date(),
            "max": sy_end.date(),
        }
    else:
        form.start_date.render_kw = {
            "min": sy_start.date().replace(year=sy_start.year + 1),
            "max": sy_end.date().replace(year=sy_end.year + 1),
        }
    form.end_date.render_kw = form.start_date.render_kw

    # form: set school year choices
    choices["school_year"] = [
        ("current", f"Actuelle ({sy_start.year} - {sy_end.year})"),
        ("next", f"Prochaine ({sy_start.year+1} - {sy_end.year+1})"),
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
    has_budget = project.has_budget() if id else None

    return render_template(
        "form.html",
        form=form,
        id=id,
        has_budget=has_budget,
        choices=choices,
        lock=lock,
    )


@main.route("/form", methods=["POST"])
@login_required
def project_form_post():
    dash = Dashboard.query.get(1)
    # get database status
    lock = dash.lock
    # get current school year dates
    sy_start, sy_end = dash.sy_start, dash.sy_end
    # set current and next school year labels
    sy_current = f"{sy_start.year} - {sy_end.year}"
    sy_next = f"{sy_start.year+1} - {sy_end.year+1}"

    # check authorizations
    if not lock:
        if "project" in session:
            id = session["project"]
        else:
            id = None
        if id:
            project = Project.query.get(id)
            if current_user.p.email not in project.teachers and current_user.p.role != "admin":
                flash("Vous ne pouvez pas modifier ce projet.", "danger")
                return redirect(url_for("main.projects"))
            elif project.status == "validated":
                flash(
                    "Ce projet a déjà été validé, la modification est impossible.",
                    "danger",
                )
                return redirect(url_for("main.projects"))
    else:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    form = ProjectForm()

    # get teachers choices for ProjectForm
    form.teachers.choices = get_teacher_choices()

    if form.validate_on_submit():
        date = get_datetime()

        if id:
            project.updated_at = date
            # get current project status
            current_status = project.status
        else:
            project = Project(
                created_at=date,
                updated_at=date,
                validated_at=None,
                nb_comments="0",
            )

        for f in form.data:
            if f in Project.__table__.columns.keys():
                if f in ["teachers", "divisions", "paths", "skills"]:
                    setattr(project, f, ",".join(form.data[f]))
                elif re.match(r"link_[1-4]$", f):
                    if form.data[f]:
                        if re.match(r"^https?://", form.data[f]):
                            setattr(project, f, form.data[f].strip())
                        else:
                            setattr(project, f, "https://" + form.data[f].strip())
                elif re.match(r"(start|end)_date", f):
                    f_t = re.sub(r"date$", "time", f)
                    if form.data[f] and form.data[f_t]:
                        f_start = datetime.combine(form.data[f], form.data[f_t])
                        setattr(project, f, f_start)
                    elif not form.data[f]:
                        setattr(project, f, f_start)
                    else:
                        f_start = form.data[f]
                        setattr(project, f, f_start)
                elif f == "status":
                    if form.data[f] != "adjust":
                        setattr(project, f, form.data[f])
                elif f == "students":
                    if form.data["requirement"] == "no" and (
                        form.data["students"] or form.data["status"] in ["ready", "validated"]
                    ):
                        students = re.sub(r" *(  +|\t+|,|\r\n)\s*", ",", form.data[f])
                        students = re.sub(
                            r"([1-6]) *(?:e|ème|de|nde|ère)? *([ABab])",
                            lambda p: f"{p.group(1)}e{p.group(2).upper()}",
                            students,
                        )
                        students = re.sub(r"0e|[Tt](a?le|erminale)", "Terminale", students)
                        # sort primarly by the name, then the class
                        students = students.split(",")
                        students = [
                            (students[i], students[i + 1], students[i + 2])
                            for i in range(0, len(students), 3)
                        ]
                        students.sort(key=lambda x: (choices["divisions"].index(x[0]), x[1]))
                        students = ",".join(f"{x[0]},{x[1]},{x[2]}" for x in students)
                        setattr(project, f, students)
                elif f == "school_year":
                    setattr(
                        project,
                        f,
                        sy_current if form.data[f] == "current" else sy_next,
                    )
                else:
                    if isinstance(form.data[f], str):
                        setattr(project, f, form.data[f].strip())
                    else:
                        setattr(project, f, form.data[f])

        # set axis data
        project.axis = project.priority[:2].replace("A", "Axe ")

        # check students list consistency with nb_students and divisions fields
        if project.requirement == "no" and (
            project.students or project.status in ["ready", "validated"]
        ):
            students = project.students.split(",")
            nb_students = len(students) // 3
            divisions = ",".join(
                sorted(
                    {students[i] for i in range(0, len(students), 3)},
                    key=choices["divisions"].index,
                )
            )
            if nb_students != project.nb_students:
                project.nb_students = nb_students
            if divisions != project.divisions:
                project.divisions = divisions

        departments = {
            Personnel.query.filter_by(email=teacher).first().department
            for teacher in form.teachers.data
        }
        setattr(project, "departments", ",".join(departments))

        # clean "invisible" budgets
        if form.data["school_year"] == "current":
            if project.start_date.year == sy_end.year:
                project.budget_hse_1 = 0
                project.budget_exp_1 = 0
                project.budget_trip_1 = 0
                project.budget_int_1 = 0
            if project.end_date.year == sy_start.year:
                project.budget_hse_2 = 0
                project.budget_exp_2 = 0
                project.budget_trip_2 = 0
                project.budget_int_2 = 0
        else:
            if project.start_date.year == sy_end.year + 1:
                project.budget_hse_1 = 0
                project.budget_exp_1 = 0
                project.budget_trip_1 = 0
                project.budget_int_1 = 0
            if project.end_date.year == sy_start.year + 1:
                project.budget_hse_2 = 0
                project.budget_exp_2 = 0
                project.budget_trip_2 = 0
                project.budget_int_2 = 0

        # database update
        if id:
            # commit project update
            db.session.commit()
            # save_projects_df(data_path, projects_file)
            session.pop("project")
            flash(f'Le projet "{project.title}" a été modifié avec succès !', "info")
            logger.info(f"Project id={id} modified by {current_user.p.email}")
            # send email notification

            if project.status.startswith("ready") and not current_status.startswith("ready"):
                error = send_notification(project.status, project)
                if error:
                    flash(error, "warning")
        else:
            current_user.projects.append(project)
            db.session.add(project)
            db.session.commit()
            # save pickle when a new project is added
            save_projects_df(data_path, projects_file)
            logger.info(f"New project added ({project.title}) by {current_user.p.email}")
            # send email notification
            if project.status.startswith("ready"):
                error = send_notification(project.status, project)
                if error:
                    flash(error, "warning")

        id = None
        return redirect(url_for("main.projects"))

    # form: set school year dates for calendar
    if form.school_year.data == "current":
        form.start_date.render_kw = {
            "min": sy_start.date(),
            "max": sy_end.date(),
        }
    else:
        form.start_date.render_kw = {
            "min": sy_start.date().replace(year=sy_start.year + 1),
            "max": sy_end.date().replace(year=sy_end.year + 1),
        }
    form.end_date.render_kw = form.start_date.render_kw

    # form: set school year choices
    choices["school_year"] = [
        ("current", f"Actuelle ({sy_start.year} - {sy_end.year})"),
        ("next", f"Prochaine ({sy_start.year+1} - {sy_end.year+1})"),
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
                form.data[f] or 0
                for f in form.data
                if re.match(r"^budget_(hse|exp|trip|int)_[12]$", f)
            ]
        )
    )

    return render_template(
        "form.html",
        form=form,
        id=id,
        has_budget=has_budget,
        choices=choices,
        lock=lock,
    )


@main.route("/project/validation", methods=["POST"])
@login_required
def validate_project():
    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)
        if current_user.p.role == "direction":
            if project.status == "ready-1":
                project.status = "validated-1"
                message = " (budget)"
            elif project.status == "ready":
                project.status = "validated"
                message = ""
            else:
                redirect(url_for("main.projects"))
            project.validated_at = get_datetime()
            db.session.commit()
            # save_projects_df(data_path, projects_file)

            flash(f'Le projet "{project.title}" a été validé{message}.', "info")

            # send email notification
            error = send_notification(project.status, project)
            if error:
                flash(error, "warning")

            logger.info(
                f"Project id={id} ({project.title}) validated by {current_user.p.email}"
            )

    return redirect(url_for("main.projects"))


@main.route("/project/update", methods=["POST"])
@login_required
def update_project():
    # get database status
    lock = Dashboard.query.get(1).lock

    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data

        # authorization checks
        if not lock:
            project = Project.query.get(id)
            if current_user.p.email not in project.teachers and current_user.p.role != "admin":
                flash("Vous ne pouvez pas modifier ce projet.", "danger")
                return redirect(url_for("main.projects"))
            elif project.status == "validated":
                flash(
                    "Ce projet a déjà été validé, la modification est impossible.",
                    "danger",
                )
                return redirect(url_for("main.projects"))
        else:
            flash("La modification des projets n'est plus possible.", "danger")

        session["project"] = id
        return redirect(url_for("main.project_form"))

    return redirect(url_for("main.projects"))


@main.route("/project/delete", methods=["POST"])
@login_required
def delete_project():
    # get database status
    lock = Dashboard.query.get(1).lock

    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)
        if not lock:
            if (
                current_user == project.user or current_user.p.role == "admin"
            ) and project.status != "validated":
                title = project.title

                db.session.query(Comment).filter(Comment.project_id == id).delete(
                    synchronize_session=False
                )
                db.session.delete(project)
                db.session.commit()
                # save_projects_df(data_path, projects_file)
                flash(f'Le projet "{title}" a été supprimé.', "info")
                logger.info(f"Project id={id} ({title}) deleted by {current_user.p.email}")
            else:
                flash("Vous ne pouvez pas supprimer ce projet.", "danger")
        else:
            flash("La suppression des projets n'est plus possible.", "danger")

    return redirect(url_for("main.projects"))


# fiche projet avec commentaires
@main.route("/project/<int:id>", methods=["GET"])
@login_required
def project(id):
    dash = Dashboard.query.get(1)
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end = dash.sy_start, dash.sy_end

    project = Project.query.get(id)

    if project:
        if current_user.p.email in project.teachers or current_user.p.role in [
            "gestion",
            "direction",
        ]:
            # remove new comment badge
            if (current_user.p.email in project.teachers and "N" in project.nb_comments) or (
                current_user.p.role in ["gestion", "direction"] and "n" in project.nb_comments
            ):
                project.nb_comments = project.nb_comments.rstrip("Nn")
                db.session.commit()
                # save_projects_df(data_path, projects_file)  # bug later reading db

            # get project data as DataFrame
            df = get_projects_df(filter=id)

            # set axes and priorities labels
            df["axis"] = df["axis"].map(axes)
            df["priority"] = df["priority"].map(priorities)

            # get project row as named tuple
            p = next(df.itertuples())

            # get comments on project as DataFrame
            dfc = get_comments_df(id)

            form = CommentForm(project=id)

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
        flash(f"Le projet demandé ({id=}) n'existe pas ou a été supprimé.", "danger")

    return redirect(url_for("main.projects"))


@main.route("/project/comment/add", methods=["POST"])
@login_required
def project_add_comment():
    form = CommentForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)

        # add comment
        if current_user.p.email in project.teachers or current_user.p.role in [
            "gestion",
            "direction",
        ]:
            date = get_datetime()
            comment = Comment(
                project=project,
                user=current_user,
                message=form.message.data,
                posted_at=date,
            )
            db.session.add(comment)
            db.session.commit()

            new = "n" if current_user.p.email in project.teachers else "N"
            project.nb_comments = f"{int(project.nb_comments.rstrip('Nn'))+1}{new}"
            if new == "N":
                project.auth = True
            db.session.commit()
            # save_projects_df(data_path, projects_file)

            # send email notification
            error = send_notification("comment", project, form.message.data)
            if error:
                flash(error, "warning")

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

        if current_user.p.email in project.teachers or current_user.p.role in [
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
                ["Encadrement (personnels LFS)", get_names(project.teachers)],
                [
                    "Encadrement (personnes extérieures)",
                    project.fieldtrip_ext_people if project.fieldtrip_ext_people else "-",
                ],
                ["Lieu et adresse", project.fieldtrip_address.replace("\r", "")],
                [
                    "Incidence sur les autres cours et AES",
                    project.fieldtrip_impact.replace("\r", "")
                    if project.fieldtrip_impact != ""
                    else "-",
                ],
                [
                    "Sortie scolaire validée \npar le chef d'établissement",
                    get_date_fr(project.validated_at),
                ],
                [
                    f"Transmis à l'Ambassade de France \n{AMBASSADE_EMAIL}",
                    get_date_fr(get_datetime()),
                ],
            ]

            filename = fieldtrip_pdf.replace("<id>", str(id))
            generate_fieldtrip_pdf(data, data_path, data_dir, filename)

            filepath = os.fspath(PurePath(data_dir, filename))
            return send_file(filepath, as_attachment=False)

    return redirect(url_for("main.projects"))


@main.route("/project/duplicate", methods=["POST"])
@login_required
def duplicate_project():
    form = SelectProjectForm()

    if form.validate_on_submit():
        # get project id
        id = form.project.data
        project = Project.query.get(id)

        # create a new project instance
        date = get_datetime()
        new_project = Project(
            title=f"{project.title} (copie)",
            created_at=date,
            updated_at=date,
            validated_at=None,
            nb_comments="0",
            status="draft",
        )

        # duplicate data
        for f in Project.__table__.columns.keys():
            if f not in [
                "id",
                "title",
                "created_at",
                "updated_at",
                "validated_at",
                "nb_comments",
                "status",
                "user_id",
            ]:
                setattr(new_project, f, getattr(project, f))

        # Add the new project to the session and commit
        current_user.projects.append(new_project)
        db.session.add(new_project)
        db.session.commit()

        # save pickle when a new project is added
        save_projects_df(data_path, projects_file)
        logger.info(f"New project added ({project.title}) by {current_user.p.email}")

    return redirect(url_for("main.projects"))


@main.route("/data", methods=["GET", "POST"])
@login_required
def data():
    dash = Dashboard.query.get(1)
    # get school year
    sy_start, sy_end = dash.sy_start, dash.sy_end

    # personnel list
    choices["teachers"] = sorted(
        [
            (
                personnel.email,
                f"{personnel.name} {personnel.firstname}",
                personnel.department,
            )
            for personnel in Personnel.query.filter(
                Personnel.role.is_(None) | (Personnel.role != "admin")
            ).all()
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
        dist[axis[0]] = (n, f"{N and n/N*100 or 0:.0f}%")  # 0 if division by zero
        for priority in choices["priorities"][choices["axes"].index(axis)]:
            p = len(df[df.priority == priority[0]])
            dist[priority[0]] = (p, f"{n and p/n*100 or 0:.0f}%", s)

    for department in choices["departments"]:
        d = len(df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")])
        s = sum(df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")]["nb_students"])
        dist[department] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    d = len(df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)])
    if len(df) != 0:
        s = sum(
            df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)][
                "nb_students"
            ]
        )
    else:
        s = 0
    dist["secondary"] = (d, f"{N and d/N*100 or 0:.0f}%", s)
    dist["primary"] = dist["Primaire"]
    dist["kindergarten"] = dist["Maternelle"]

    for teacher in choices["teachers"]:
        d = len(df[df.teachers.str.contains(teacher[0])])
        s = sum(df[df.teachers.str.contains(teacher[0])]["nb_students"])
        dist[teacher[0]] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    choices["paths"] = ProjectForm().paths.choices
    for path in choices["paths"]:
        d = len(df[df.paths.str.contains(path)])
        s = sum(df[df.paths.str.contains(path)]["nb_students"])
        dist[path] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    choices["skills"] = ProjectForm().skills.choices
    for skill in choices["skills"]:
        d = len(df[df.skills.str.contains(skill)])
        s = sum(df[df.skills.str.contains(skill)]["nb_students"])
        dist[skill] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    for section in ["secondaire", "primaire", "maternelle"]:
        dist[section] = len(
            df[~df.divisions.str.split(",").map(set(choices[section]).isdisjoint)]
        )
        n = dist[section]
        for division in choices[section]:
            d = len(df[df.divisions.str.contains(division)])
            dist[division] = (d, f"{n and d/n*100 or 0:.0f}%")

    choices["mode"] = ProjectForm().mode.choices
    for m in choices["mode"]:
        d = len(df[df["mode"] == m])
        s = sum(df[df["mode"] == m]["nb_students"])
        dist[m] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    choices["requirement"] = ProjectForm().requirement.choices
    for r in choices["requirement"]:
        d = len(df[df.requirement == r[0]])
        s = sum(df[df.requirement == r[0]]["nb_students"])
        dist[r[0]] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    choices["location"] = ProjectForm().location.choices
    for loc in choices["location"]:
        d = len(df[df.location == loc[0]])
        s = sum(df[df.location == loc[0]]["nb_students"])
        dist[loc[0]] = (d, f"{N and d/N*100 or 0:.0f}%", s)

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
    graph_html = sunburst_chart(dfa) if graph_module else "Ressources serveur insuffisantes."

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
    graph_html3 = timeline_chart(dft) if graph_module else "Ressources serveur insuffisantes."

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
    # get application dashboard
    dash = Dashboard.query.get(1)
    # get current school year dates
    sy_start, sy_end = dash.sy_start, dash.sy_end
    # set current and next school year labels
    sy_current = f"{sy_start.year} - {sy_end.year}"
    sy_next = f"{sy_start.year+1} - {sy_end.year+1}"

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
        fy = str(sy_start.year) if sy_start.year == datetime.now().year else str(sy_end.year)
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
            # User=User,
            # Project=Project,
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
                filepath = os.fspath(PurePath(data_path, data_dir, filename))
                df.to_excel(
                    filepath,
                    sheet_name="Projets pédagogiques LFS",
                    columns=df.columns,
                )
                filepath = os.fspath(PurePath(data_dir, filename))
                return send_file(filepath, as_attachment=True)

    return Response(status=HTTPStatus.NO_CONTENT)


@main.route("/language/<language>")
def set_language(language="fr"):
    response = make_response(redirect(request.referrer or "/"))
    response.set_cookie("lang", language)
    return response
