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
    send_from_directory,
)

from flask_login import login_required, current_user

from sqlalchemy import case
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError

from http import HTTPStatus

from datetime import datetime, time

import os

import pandas as pd
import pickle
import re

from . import db, data_path, app_version, production_env, logger, gmail_service
from ._version import __version__

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

from .utils import (
    get_datetime,
    get_date_fr,
    get_project_dates,
    get_name,
    get_default_sy_dates,
    auto_school_year,
    row_to_dict,
    get_label,
    get_projects_df,
)

from .data import data_analysis

if gmail_service:
    from .communication import send_notification

try:
    from .print import prepare_field_trip_data, generate_fieldtrip_pdf

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


def get_member_choices():
    """Get the list of members with departments for members input field in form"""
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


def get_school_year_choices():
    """Get the list of school years for the school year selection form"""
    school_years = sorted([sy.sy for sy in SchoolYear.query.all()], reverse=True)
    if len(school_years) > 1:
        school_years.insert(0, "Toutes les années")
        school_years.insert(1, "Projet Étab. 2024 - 2027")
    return school_years


def get_comments_df(id):
    """Convert ProjectComment table to DataFrame"""
    if db.session.query(ProjectComment.id).count() != 0:
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
        for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
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


def handle_db_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(f"Database error in {f.__name__}: {str(e)}")
            db.session.rollback()
            flash(
                "Une erreur est survenue lors de l'accès à la base de données.", "danger"
            )
            return redirect(url_for("main.projects"))

    return decorated_function


@main.route("/favicon.ico")  # for legacy browsers
def favicon():
    return send_from_directory(
        os.path.join(main.root_path, "static"),
        "assets/favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@main.route("/android-chrome-192x192.png")  # for chromium browsers
def android_chrome_192x192():
    return send_from_directory(
        os.path.join(main.root_path, "static"),
        "assets/android-chrome-192x192.png",
        mimetype="image/png",
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
@handle_db_errors
def dashboard():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("main.projects"))

    # get database status
    auto_dashboard()
    dash = Dashboard.query.first()
    lock = dash.lock
    lock_message = dash.lock_message

    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # get default school year dates
    sy_start_default, sy_end_default = get_default_sy_dates()

    # automatic school year settings
    if sy_start == sy_start_default and sy_end == sy_end_default:
        sy_auto = True
    else:
        sy_auto = False

    # get total number of projects
    n_projects = db.session.query(Project.id).count()

    # form for setting database status
    form = LockForm()

    # form for setting school year dates
    form3 = SetSchoolYearForm()

    if current_user.p.role == "admin" or (
        current_user.p.role in ["gestion", "direction"] and lock != 2
    ):
        # set database status
        if form.validate_on_submit():
            if form.lock.data == "Ouvert":
                lock = 0
            elif current_user.p.role == "admin":
                lock = 2
            else:
                lock = 1
            dash.lock = lock
            dash.lock_message = "La base est momentanément <span class='has-text-danger'><strong>fermée pour maintenance</strong></span> de l'application. La consultation reste ouverte."
            db.session.commit()
            lock_message = dash.lock_message

        # set school year dates
        if form3.sy_submit.data and form3.validate_on_submit():
            sy_auto = form3.sy_auto.data
            sy_start = form3.sy_start.data
            sy_end = form3.sy_end.data
            auto_school_year(sy_start, sy_end)

    else:
        flash("Attention maintenance : modification impossible.", "danger")

    # database status form set to the opposite value to serve as a toogle button
    form.lock.data = "Fermé" if not lock else "Ouvert"

    # school year dates
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
@handle_db_errors
def projects():
    # get database status
    auto_dashboard()
    dash = Dashboard.query.first()
    lock = dash.lock
    lock_message = dash.lock_message

    # get school year
    sy_start, sy_end, sy = auto_school_year()

    ## filter selection
    form2 = ProjectFilterForm()

    if form2.validate_on_submit():
        session["filter"] = form2.filter.data

    if "filter" not in session:  # default
        if current_user.p.role in ["gestion", "direction", "admin"]:
            session["filter"] = "LFS"
        else:
            session["filter"] = current_user.p.department

    form2.filter.data = session["filter"]

    # get school year choices
    form3 = SelectSchoolYearForm()
    form3.sy.choices = get_school_year_choices()
    schoolyears = len(form3.sy.choices) > 1

    # school year selection
    if form3.validate_on_submit():
        if form3.sy.data == "Toutes les années":
            session["sy"] = None
        else:
            session["sy"] = form3.sy.data

    if "sy" not in session:
        session["sy"] = sy

    form3.sy.data = session["sy"]

    # get projects DataFrame
    if session["filter"] in ["Mes projets", "Mes projets à valider"]:
        df = get_projects_df(current_user.p.department, sy=session["sy"])
        df = df[
            df["members"].apply(lambda x: str(current_user.p.id) in x.split(","))
            | (df["pid"] == current_user.p.id)
        ]
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
@handle_db_errors
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
        if current_user.id != project.uid and not any(
            member.pid == current_user.pid for member in project.members
        ):
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
            data["created_at"] = None
            data["modified_at"] = None
            data["modified_by"] = None
            data["validated_at"] = None
            data["validated_by"] = None
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
@handle_db_errors
def project_form_post():
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock
    # get school year
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
        if current_user.id != project.uid and not any(
            member.pid == current_user.pid for member in project.members
        ):
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
            # update existing project
            # create new record history
            if project.validated_at and project.validated_at > project.modified_at:
                history_entry = ProjectHistory(
                    project_id=project.id,
                    updated_at=project.validated_at,
                    updated_by=project.validated_by,
                    status=project.status,
                )
            else:
                history_entry = ProjectHistory(
                    project_id=project.id,
                    updated_at=project.modified_at,
                    updated_by=project.modified_by,
                    status=project.status,
                )

            # update project modification date and user
            setattr(project, "modified_at", date)
            setattr(project, "modified_by", current_user.id)

            # get project current status
            previous_status = project.status
            previous_members = [member.pid for member in project.members]
        else:
            # create new project
            project = Project(
                created_at=date,
                uid=current_user.id,
                modified_at=date,
                modified_by=current_user.id,
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
                    else:
                        data = ""
                elif f == "school_year":
                    data = sy_current if form_data == "current" else sy_next
                elif f in ["fieldtrip_ext_people", "fieldtrip_impact"]:
                    if re.match(r"(?ai)aucun|non|sans objet|néant", form_data):
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

                # update project history
                if id and f in ProjectHistory.__table__.columns.keys():
                    # check if field has changed
                    if getattr(project, f) != data:
                        setattr(history_entry, f, getattr(project, f))

                # update project
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

        # update school years
        if not id:  # new project
            school_year = SchoolYear.query.filter(
                SchoolYear.sy == project.school_year
            ).first()
            if school_year:
                school_year.nb_projects += 1
            else:  # next school year
                school_year = SchoolYear(
                    sy_start=sy_start.replace(year=sy_start.year + 1),
                    sy_end=sy_end.replace(year=sy_end.year + 1),
                    sy=sy_next,
                    nb_projects=1,
                )
                db.session.add(school_year)

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
        # if not id:
        #    save_projects_df(data_path, projects_file)

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


# historique du projet
@main.route("/history/<int:id>", methods=["GET"])
@login_required
def history(id):
    project = Project.query.get(id)
    if project:
        if (
            current_user.id == project.uid
            or any(member.pid == current_user.pid for member in project.members)
            or current_user.p.role
            in [
                "gestion",
                "direction",
            ]
        ):
            # create a list of triplets (status, updated_at, updated_by)
            if project.validated_at and project.validated_at > project.modified_at:
                project_history = [
                    (project.status, project.validated_at, project.validated_by)
                ]
            else:
                project_history = [
                    (project.status, project.modified_at, project.modified_by)
                ]

            project_history += [
                (entry.status, entry.updated_at, entry.updated_by)
                for entry in project.history
            ]

            if current_user.p.role in ["gestion", "direction"]:
                # remove all draft modification events prior to first validation request
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
            {"Erreur": "Vous ne pouvez pas accéder à l'historique de ce projet."}
        ), 404
    else:
        return jsonify(
            {"Erreur": f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé."}
        ), 404


@main.route("/project/validation/<int:id>", methods=["GET"])
@login_required
@handle_db_errors
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
        updated_at=project.modified_at,
        updated_by=project.modified_by,
        status=project.status,
    )
    db.session.add(history_entry)

    # update project
    date = get_datetime()
    project.validated_at = date
    project.validated_by = current_user.id

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
            message = f'Le budget du projet "{project.title}" '
        message += "a été approuvé"
    else:
        message += "a été validé"
    message += " avec succès !"
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
@handle_db_errors
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
        updated_at=project.validated_at,
        updated_by=project.validated_by,
        status=project.status,
    )
    db.session.add(history_entry)
    db.session.flush()

    # update project
    date = get_datetime()
    project.validated_at = date
    project.validated_by = current_user.id

    if project.status == "validated":
        project.status = "validated-10"
    else:
        db.session.rollback()
        flash(f"Erreur : statut inconnu ({project.status}). Action annulée.", "danger")
        redirect(url_for("main.projects"))

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
    dash = Dashboard.query.first()
    lock = dash.lock

    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("main.projects"))

    project = Project.query.get(id)
    if project:
        if current_user.id == project.uid and project.status != "validated":
            title = project.title
            try:
                # update school years
                school_year = SchoolYear.query.filter(
                    SchoolYear.sy == project.school_year
                ).first()
                school_year.nb_projects -= 1
                # delete the school year if no projects and not the current one
                if project.school_year != sy and school_year.nb_projects == 0:
                    db.session.delete(school_year)

                # delete project
                db.session.delete(project)

                # update database
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
                flash(f'Erreur : suppression impossible du projet "{title}."', "danger")
        else:
            flash("Vous ne pouvez pas supprimer ce projet.", "danger")
    else:
        flash(f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.", "danger")

    return redirect(url_for("main.projects"))


# fiche projet avec commentaires
@main.route("/project/<int:id>", methods=["GET"])
@login_required
@handle_db_errors
def project(id):
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    project = Project.query.get(id)

    if project:
        if (
            current_user.id == project.uid
            or any(member.pid == current_user.pid for member in project.members)
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

            # get project DataFrame
            df = get_projects_df(filter=id)

            # set axes and priorities labels
            df["axis"] = df["axis"].map(axes)
            df["priority"] = df["priority"].map(priorities)

            # get project row as named tuple
            p = next(df.itertuples())

            # get project comments DataFrame
            dfc = get_comments_df(id)

            # get e-mail notification recipients
            recipients = get_comment_recipients(project)

            # set comment form data
            if recipients:
                form = CommentForm(
                    project=id, recipients=",".join([str(pid) for pid in recipients])
                )
                # display recipients names in the message field description
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


@main.route("/project/comment/add", methods=["POST"])
@login_required
@handle_db_errors
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
        if (
            current_user.id == project.uid
            or any(member.pid == current_user.pid for member in project.members)
            or current_user.p.role
            in [
                "gestion",
                "direction",
            ]
        ):
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
                        flash("Notification envoyée avec succès !", "info")
                        logger.info(
                            f"New comment on project id={project.id} sent by {current_user.p.email}."
                        )
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


@main.route("/project/print/<int:id>", methods=["GET"])
@login_required
@handle_db_errors
def print_fieldtrip_pdf(id):
    # get project id
    project = Project.query.get(id)

    if not project or not (
        current_user.id == project.uid
        or any(member.pid == current_user.pid for member in project.members)
        or current_user.p.role
        in [
            "gestion",
            "direction",
            "admin",
        ]
    ):
        return redirect(url_for("main.projects"))

    if not matplotlib_module:
        flash(
            "Ressources serveur insuffisantes pour générer la fiche de sortie scolaire.",
            "danger",
        )
        return redirect(url_for("main.projects"))

    # PDF file path
    filename = fieldtrip_pdf.replace("<id>", str(id))
    pdf_file_path = data_path / filename

    # generate PDF if file does not exists
    if current_user.p.role in [
        "gestion",
        "direction",
        "admin",
    ] or not os.path.exists(pdf_file_path):
        # prepare data
        data = prepare_field_trip_data(project)
        # generate PDF document
        generate_fieldtrip_pdf(data, pdf_file_path)

    return send_file(pdf_file_path, as_attachment=False)


@main.route("/data", methods=["GET", "POST"])
@login_required
def data():
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # get school year choices
    form3 = SelectSchoolYearForm()
    form3.sy.choices = get_school_year_choices()
    schoolyears = len(form3.sy.choices) > 1

    # default to current school year if not in session
    if "sy" not in session:
        session["sy"] = sy

    # school year selection
    if form3.validate_on_submit():
        if form3.sy.data == "Toutes les années":
            session["sy"] = None
        else:
            session["sy"] = form3.sy.data

    form3.sy.data = session["sy"]

    if request.method == "GET":
        # return a "working..." waiting page
        # form POST request on page load
        return render_template(
            "_data.html",
            form3=form3,
            schoolyears=schoolyears,
        )

    # generate data analysis
    df, choices, dist, graph_html, graph_html2, graph_html3 = data_analysis(session["sy"])

    return render_template(
        "data.html",
        df=df,
        choices=choices,
        dist=dist,
        graph_html=graph_html,
        graph_html2=graph_html2,
        graph_html3=graph_html3,
        form3=form3,
        schoolyears=schoolyears,
    )


@main.route("/budget", methods=["GET", "POST"])
@login_required
@handle_db_errors
def budget():
    # check for authorized user
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("main.projects"))

    # get school year
    sy_start, sy_end, sy = auto_school_year()
    # set current and next school year labels
    sy_current = sy
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    ### school year tab ###
    form = SelectSchoolYearForm()

    # set school year choices
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
@handle_db_errors
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
@handle_db_errors
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
