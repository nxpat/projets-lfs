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

from sqlalchemy import case, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from functools import wraps
from itertools import groupby
from operator import attrgetter

from http import HTTPStatus

from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta

import os

import pandas as pd
import pickle
import re

import markdown
import bleach
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from . import db, data_path, app_version, is_production, logger, gmail_service_api
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
    QueuedAction,
)

from .project import (
    ProjectForm,
    CommentForm,
    SelectProjectForm,
    LockForm,
    ProjectFilterForm,
    SelectYearsForm,
    DownloadForm,
    create_schoolyear_config_form,
    levels,
    choices,
    valid_division,
)

from .utils import (
    get_datetime,
    get_date_fr,
    get_project_dates,
    get_name,
    get_default_sy_dates,
    auto_school_year,
    division_name,
    division_names,
    get_divisions,
    get_label,
    get_projects_df,
)

from .data import data_analysis

if gmail_service_api:
    from .notifications import send_notification

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
APP_BASE_URL = os.getenv("APP_BASE_URL")
BOOMERANG_WEBSITE = os.getenv("BOOMERANG_WEBSITE")
APP_DOMAIN = os.getenv("APP_DOMAIN")

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


def get_school_year_choices(sy, sy_next):
    return [
        ("current", f"Actuelle ({sy})"),
        ("next", f"Prochaine ({sy_next})"),
    ]


def get_calendar_constraints(form, sy_start, sy_end):
    # for the current school year
    choices["sy_date_min"] = sy_start
    choices["sy_date_max"] = sy_end

    # for the next school year
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"
    next_school_year = SchoolYear.query.filter(SchoolYear.sy == sy_next).first()
    if next_school_year:
        choices["sy_next_date_min"] = next_school_year.sy_start
        choices["sy_next_date_max"] = next_school_year.sy_end
    else:
        choices["sy_next_date_min"] = sy_end + timedelta(1)
        choices["sy_next_date_max"] = sy_end + (sy_end - sy_start)

    # set date input constraints
    if form.school_year.data == "current":
        date_constraints = {"min": sy_start, "max": sy_end}
    else:
        date_constraints = {
            "min": choices["sy_next_date_min"],
            "max": choices["sy_next_date_max"],
        }
    form.start_date.render_kw = date_constraints
    form.end_date.render_kw = date_constraints

    return form


def get_member_choices():
    """Get the list of members with departments for members input field in form"""
    # Fetch all personnel for the relevant departments
    # We only fetch the columns we need (id, firstname, name, department)
    all_personnel = (
        Personnel.query.filter(Personnel.department.in_(choices["departments"]))
        .order_by(Personnel.department, Personnel.name)  # Order by dept first for groupby
        .all()
    )

    # Group the results
    result = {}
    for dept, group in groupby(all_personnel, key=attrgetter("department")):
        result[dept] = [(str(p.id), f"{p.firstname} {p.name}") for p in group]

    return result


def get_divisions_choices(sy):
    return [(div, division_name(div)) for div in get_divisions(sy)]


def get_divisions_ux_choices(form):
    return {
        section: [
            subfield
            for subfield in form.divisions
            if subfield.data.startswith(tuple(levels[section]))
        ]
        for section in ["Lycée", "Collège", "Élémentaire", "Maternelle"]
    }


def get_status_choices(form, project_status=None):
    if project_status in [None, "draft", "ready-1"]:
        form.status.choices = [choices["status"][i] for i in [0, 1, 3]]
    elif project_status == "validated-1":
        form.status.choices = choices["status"][2:4]
        form.status.description = "Le projet sera ajusté ou soumis à validation"
    elif project_status == "ready":
        form.status.choices = [choices["status"][4]]
        form.status.description = "Le projet, déjà soumis à validation, sera ajusté"
        form.status.data = "adjust"
    else:
        form.status.choices = [choices["status"][0]]
        form.status.description = "Le projet sera conservé comme brouillon"
    return form


def get_years_choices(fy=False):
    """Return school years and fiscal years form choices"""
    school_years = sorted([(sy.sy, sy.sy) for sy in SchoolYear.query.all()], reverse=True)
    if fy:
        fiscal_years = sorted(
            list(set([y for sy in school_years for y in sy[0].split(" - ")])), reverse=True
        )
    if len(school_years) > 1:
        school_years.insert(0, ("Toutes les années", "Toutes les années"))
        school_years.insert(1, ("2024 - 2027", "Projet Étab. 2024 - 2027"))
    if fy:
        return school_years, fiscal_years
    else:
        return school_years


def get_axis(priority):
    for axis, priorities in choices["pe"].items():
        if priority in priorities:
            return axis
    return None


def get_comments_df(project_id):
    """Convert ProjectComment table to DataFrame"""
    # Build a query that joins Comment -> User -> Personnel
    # We select exactly the columns we need for the DataFrame
    query = (
        db.session.query(
            ProjectComment.id,
            Personnel.id.label("pid"),
            ProjectComment.message,
            ProjectComment.posted_at,
        )
        .join(User, ProjectComment.uid == User.id)
        .join(Personnel, User.p)
        .filter(ProjectComment.project_id == project_id)
    )

    df = pd.read_sql(query.statement, db.engine)

    # 3. Handle empty case and formatting
    if df.empty:
        return pd.DataFrame(columns=["id", "pid", "message", "posted_at"]).set_index("id")

    # Ensure pid is a string if that's required by your logic
    df["pid"] = df["pid"].astype(str)

    return df.set_index("id")


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

    # add users with "gestion" role and "email=default-c" preferences
    gestionnaires_query = (
        db.session.query(Personnel)
        .options(joinedload(Personnel.user))
        .filter(Personnel.role == "gestion")
        .all()
    )

    # 2. Filter the preference strings in Python
    target_pref = "email=default-c"

    gestionnaires = [
        p.id
        for p in gestionnaires_query
        if p.user and p.user.preferences and target_pref in p.user.preferences.split(",")
    ]

    # remove duplicates and remove current user
    recipients = set([creator] + members + users + gestionnaires)
    recipients.discard(current_user.pid)

    return list(recipients)


def md_to_html(raw_markdown):
    """
    Converts raw markdown to sanitized HTML.
    """
    if not raw_markdown:
        return ""

    # 1. Convert Markdown to HTML with common extensions
    # 'extra' includes tables, attribute lists, and abbreviations
    # 'nl2br' converts newlines to <br> tags (optional)
    html = markdown.markdown(
        raw_markdown,
        extensions=["extra", "nl2br"],
    )

    # 2a. Use BeautifulSoup to inject Bulma classes
    soup = BeautifulSoup(html, "html.parser")

    mapping = {
        "h1": ["title", "is-5", "mb-2"],
        "h2": ["subtitle", "is-6"],
        "ul": ["mt-2"],
        "table": ["table", "is-striped", "is-hoverable"],
    }

    for tag, classes in mapping.items():
        for element in soup.find_all(tag):
            element["class"] = element.get("class", []) + classes

    # 2b. Mark external links
    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Check if the link is absolute and points to a different domain
        parsed_url = urlparse(href)
        if parsed_url.scheme in ["http", "https"] and parsed_url.netloc != APP_DOMAIN:
            # Set security attributes for external links
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"

            # Set the icon
            icon = soup.new_tag("i")
            icon["class"] = "si fa--arrow-up-right-from-square is-size-7 ml-1"
            icon["aria-hidden"] = "true"

            # Append the icon inside the anchor tag after the text
            a.append(icon)

    html = str(soup)

    # 3. Define the security whitelist
    allowed_tags = [
        "p",
        "br",
        "div",
        "strong",
        "em",
        "h1",
        "h2",
        "ul",
        "ol",
        "li",
        "code",
        "pre",
        "blockquote",
        "hr",
        "a",
        "i",
        "span",
        "img",
        "sup",
        "sub",
        "table",
        "tbody",
        "thead",
        "tr",
        "th",
        "td",
    ]
    allowed_attrs = {
        "*": ["class", "id", "aria-hidden"],
        "a": ["href", "title", "rel", "target"],
        "img": ["src", "alt", "title", "width", "height"],
    }

    # 4. Scrub the HTML
    return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)


def update_database():
    """
    Update the database tables for projects

    This function performs the following updates:

    1. **Project Table**:
    - Update divisions to use the new canonical divisions: mps et mgs

    """

    # Update flag
    update = False

    # Get all projects
    projects = Project.query.all()

    # Project: update divisions
    n_update_project_divisions = 0
    for project in projects:
        update_divisions = False
        divisions = project.divisions

        if "msgs" in divisions:
            divisions = divisions.replace("msgs", "mgs")
            update_divisions = True
        if "psms" in divisions:
            divisions = divisions.replace("psms", "pms")
            update_divisions = True

        if update_divisions:
            project.divisions = divisions
            update = True
            n_update_project_divisions += 1

    # Update database if changes were made
    if update:
        db.session.commit()
        print("The database has been updated successfully!")
        print("Statistics:")
        print(f"{n_update_project_divisions=}")
    else:
        print("No update necessary!")


@main.app_template_filter("markdown")
def markdown_filter(text):
    return md_to_html(text)


@main.context_processor
def utility_processor():
    def at_by(at_date, pid=None, uid=None, name=None, option="s"):
        return f"{get_date_fr(at_date)} par {name if name else get_name(pid, uid, option)}"

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
        elif status == "rejected":
            return 5

    return dict(
        get_date_fr=get_date_fr,
        at_by=at_by,
        get_name=get_name,
        get_label=get_label,
        levels=levels,
        choices=choices,
        division_name=division_name,
        division_names=division_names,
        get_project_dates=get_project_dates,
        krw=krw,
        regex_replace=re.sub,
        regex_search=re.search,
        get_validation_rank=get_validation_rank,
        __version__=__version__,
        is_production=is_production,
        AUTHOR=AUTHOR,
        REFERENT_NUMERIQUE_EMAIL=REFERENT_NUMERIQUE_EMAIL,
        GITHUB_REPO=GITHUB_REPO,
        LFS_LOGO=LFS_LOGO,
        LFS_WEBSITE=LFS_WEBSITE,
        APP_BASE_URL=APP_BASE_URL,
        BOOMERANG_WEBSITE=BOOMERANG_WEBSITE,
    )


def handle_db_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(
                f"Database error in {f.__name__}: {str(e)} for user {get_name(current_user.p.id)}"
            )
            db.session.rollback()
            flash(
                "Une erreur est survenue lors de l'accès à la base de données.",
                "danger",
            )
            return redirect(url_for("projects.list_projects"))

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
    return render_template("index.html")


@main.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    # get database status
    auto_dashboard()
    dash = Dashboard.query.first()
    lock = dash.lock
    lock_message = dash.lock_message

    update_database()

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
    form3 = SelectYearsForm()
    form3.years.choices = get_years_choices()
    schoolyears = len(form3.years.choices) > 1

    ## school year selection
    if form3.validate_on_submit():
        if form3.years.data == "Toutes les années":
            session["sy"] = None
        else:
            session["sy"] = form3.years.data

    if "sy" not in session:
        session["sy"] = sy

    form3.years.data = session["sy"]

    # get projects DataFrame
    if session["filter"] in ["Mes projets", "Mes projets à valider"]:
        df = get_projects_df(current_user.p.department, years=session["sy"])
        df = df[
            df["members"].apply(lambda x: str(current_user.pid) in x.split(","))
            | (df["uid"] == current_user.id)
        ]
        if session["filter"] == "Mes projets à valider":
            df = df[(df.status == "ready-1") | (df.status == "ready")]
    elif current_user.p.role in ["gestion", "direction", "admin"]:
        if session["filter"] in ["LFS", "Projets à valider"]:
            df = get_projects_df(years=session["sy"])
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            df = get_projects_df(session["filter"], years=session["sy"])
    else:
        if session["filter"] in [current_user.p.department, "Projets à valider"]:
            df = get_projects_df(current_user.p.department, years=session["sy"])
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            if session["filter"] == "LFS":
                df = get_projects_df(years=session["sy"], draft=False)
            else:
                df = get_projects_df(
                    session["filter"],
                    years=session["sy"],
                    draft=False,
                    labels=True,
                )
            df = df[df.status != "ready-1"]

    if current_user.p.role not in ["gestion", "direction", "admin"]:
        form2.filter.choices = choices["filter-user"]

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
            f"{m} message{'s' if m > 1 else ''} non lu{'s' if m > 1 else ''}" if m > 0 else ""
        )
        message += " et " if m and p else ""
        message += (
            f"{p} projet{'s' if p > 1 else ''} non-validé{'s' if p > 1 else ''}" if p > 0 else ""
        )
        message += "."
        flash(message, "warning")

    # queued action
    queued_action = QueuedAction.query.filter(
        QueuedAction.uid == current_user.id, QueuedAction.status == "pending"
    ).first()
    action_id = queued_action.id if queued_action else None

    return render_template(
        "projects.html",
        df=df,
        sy_start=sy_start,
        sy_end=sy_end,
        sy=sy,
        lock=lock,
        lock_message=lock_message,
        form=SelectProjectForm(),
        form2=form2,
        form3=form3,
        schoolyears=schoolyears,
        action_id=action_id,
    )


@main.route("/form", methods=["GET"])
@main.route("/form/<int:id>/<req>", methods=["GET"])
@login_required
def project_form(id=None, req=None):
    # get database status
    lock = Dashboard.query.first().lock

    # get school year
    sy_start, sy_end, sy = auto_school_year()
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(url_for("projects.list_projects"))

    # check for valid request
    if id and req not in ["duplicate", "update"]:
        flash("Requête non valide sur un projet.", "danger")
        return redirect(url_for("projects.list_projects"))

    # check access rights to project
    if id:
        project = Project.query.filter(Project.id == id).first()
        if not project:
            flash(
                f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.",
                "danger",
            )
            return redirect(url_for("projects.list_projects"))
        if current_user.id != project.uid and not any(
            member.pid == current_user.pid for member in project.members
        ):
            flash("Vous ne pouvez pas modifier ou dupliquer ce projet.", "danger")
            return redirect(url_for("projects.list_projects"))

        if project.status == "validated" and req != "duplicate":
            flash(
                "Ce projet a déjà été validé, la modification est impossible.",
                "danger",
            )
            return redirect(request.referrer)

        if project.status == "rejected" and req != "duplicate":
            flash(
                "Un projet non retenu ne peut plus être modifié.",
                "danger",
            )
            return redirect(request.referrer)

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

    ## form: set dynamic field choices
    # form: set school_year choices
    form.school_year.choices = get_school_year_choices(sy, sy_next)

    # form UX+JS: set calendar constraints for project dates
    form = get_calendar_constraints(form, sy_start, sy_end)

    # form: set members choices
    form.members.choices = get_member_choices()

    # form: set divisions choices
    form.divisions.choices = get_divisions_choices(sy)

    # form UX: this dictionary will hold the actual checkbox objects
    choices["divisions_ux"] = get_divisions_ux_choices(form)

    # form: set status choices and descriptions
    if id:
        form = get_status_choices(form, form.status.data)
    else:
        form = get_status_choices(form)

    # form UX: project has budget ?
    has_budget = project.has_budget() if id else False
    if id:
        form.budget.data = "Oui" if has_budget else "Non"

    return render_template(
        "form.html",
        form=form,
        has_budget=has_budget,
        lock=lock,
    )


@main.route("/form", methods=["POST"])
@login_required
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
        return redirect(url_for("projects.list_projects"))

    form = ProjectForm()

    # get project id
    id = form.id.data

    # check access rights to project
    if id:
        project = Project.query.filter(Project.id == id).first()
        if not project:
            flash(
                f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.",
                "danger",
            )
            return redirect(url_for("projects.list_projects"))

        if current_user.id != project.uid and not any(
            member.pid == current_user.pid for member in project.members
        ):
            flash("Vous ne pouvez pas modifier ce projet.", "danger")
            return redirect(url_for("projects.list_projects"))

        if project.status == "validated":
            flash(
                "Ce projet a déjà été validé, la modification est impossible.",
                "danger",
            )
            return redirect(request.referrer)

    ## from: set dynamic field choices
    # form: set members choices
    form.members.choices = get_member_choices()

    # form: set divisions choices
    form.divisions.choices = get_divisions_choices(sy)

    # form: set status choices and descriptions
    form = get_status_choices(form, project.status if id else None)

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
                        form_data or form.status.data in ["ready", "adjust"]
                    ):
                        students = form_data.strip().splitlines()
                        # keep only non-empty lines
                        students = [line for line in students if line]
                        # get valid divisions
                        canonical_divisions = [div[0] for div in form.divisions.choices]
                        for i in range(len(students)):
                            student = re.split(r" *\t+ *| *, *|  +", students[i].strip())
                            if len(form.divisions.data) == 1 and len(student) == 2:
                                # tilte() student name
                                student = [student[i].strip().title() for i in range(2)]
                                # insert class name
                                student.insert(0, division_name(form.divisions.data[0]))
                            else:
                                # title() student name
                                student = [
                                    (student[j].strip() if j == 0 else student[j].strip().title())
                                    for j in range(3)
                                ]
                                # reformat to division display name
                                student[0] = division_name(
                                    valid_division(student[0], canonical_divisions)
                                )

                            students[i] = tuple(student)

                        # sort by student name, then by class
                        students.sort(
                            key=lambda x: (
                                [d[1] for d in form.divisions.choices].index(x[0]),
                                x[1],
                            )
                        )
                        students = "\r\n".join(f"{x[0]}, {x[1]}, {x[2]}" for x in students)
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
                    if f == "fieldtrip_ext_people":
                        data = data.replace(" et ", ",")
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
        setattr(project, "axis", get_axis(form.priority.data))

        # set project departments
        member_ids = [int(id) for id in form.members.data]

        results = (
            db.session.query(Personnel.department)
            .filter(Personnel.id.in_(member_ids))
            .distinct()
            .all()
        )

        departments = {r.department for r in results}

        setattr(project, "departments", ",".join(departments))

        # check students list consistency with nb_students and divisions fields
        if project.requirement == "no" and (project.students or project.status == "ready"):
            students = project.students.splitlines()
            nb_students = len(students)
            division_choices = [d[0] for d in form.divisions.choices]
            divisions = ",".join(
                sorted(
                    {
                        valid_division(student.split(", ")[0], division_choices)
                        for student in students
                    },
                    key=division_choices.index,
                )
            )
            if nb_students != project.nb_students:
                setattr(project, "nb_students", nb_students)
            if divisions != project.divisions:
                setattr(project, "divisions", divisions)

        # remove useless inputs
        if project.requirement == "yes":
            setattr(project, "students", None)
        if project.location not in ["outer", "trip"]:
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
            school_year = SchoolYear.query.filter(SchoolYear.sy == project.school_year).first()
            if school_year:
                school_year.nb_projects += 1
            else:  # next school year
                school_year = SchoolYear(
                    sy_start=sy_start.replace(year=sy_start.year + 1),
                    sy_end=sy_end.replace(year=sy_end.year + 1),
                    sy=sy_next,
                    nb_projects=1,
                    divisions=",".join(get_divisions(sy)),
                )
                db.session.add(school_year)

        # send email notification if status=ready-1 or status=ready
        warning_flash = None
        if project.status.startswith("ready") and project.status != previous_status:
            if gmail_service_api:
                async_action = QueuedAction(
                    uid=current_user.id,
                    timestamp=get_datetime(),
                    status="pending",
                    action_type="send_notification",
                    parameters=f"{project.status},{project.id}",
                )
                db.session.add(async_action)
            else:
                warning_flash = "API GMail non connectée : aucune notification envoyée par e-mail."

        # update database
        db.session.commit()

        # flash and log information
        if id:
            flash(
                f"Le projet <strong>{project.title}</strong> <br>a été modifié avec succès !",
                "info",
            )
            logger.info(f"Project id={id} modified by {current_user.p.email}")
        else:
            flash(
                f"Le projet <strong>{project.title}</strong> <br>a été créé avec succès !", "info"
            )
            logger.info(f"New project added ({project.title}) by {current_user.p.email}")

        if warning_flash:
            flash(warning_flash, "warning")

        # save pickle when a new project is added
        # if not id:
        #    save_projects_df(data_path, projects_file)

        return redirect(url_for("projects.list_projects"))

    ## form: set dynamic field choices
    # form: set school_year choices
    form.school_year.choices = get_school_year_choices(sy, sy_next)

    # form UX+JS: set calendar constraints for project dates
    form = get_calendar_constraints(form, sy_start, sy_end)

    # form UX: this dictionary will hold the actual checkbox objects
    choices["divisions_ux"] = get_divisions_ux_choices(form)

    # form UX: project has budget ?
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
    form.budget.data = "Oui" if has_budget else "Non"

    return render_template(
        "form.html",
        form=form,
        has_budget=has_budget,
        lock=lock,
    )


# asynchronous actions
@main.route("/action/<int:action_id>", methods=["GET"])
@login_required
def async_action(action_id):
    action = QueuedAction.query.filter(
        QueuedAction.uid == current_user.id, QueuedAction.id == action_id
    ).first()

    if action:
        if action.action_type == "send_notification" and action.status == "pending":
            parameters = action.parameters.split(",")

            # new comment notification
            if parameters[0] == "comment":
                project = Project.query.filter(Project.id == int(parameters[1])).first()
                if project:
                    comment = ProjectComment.query.filter(
                        ProjectComment.id == int(parameters[2])
                    ).first()
                    if comment:
                        recipients = action.options.split(",")
                        error = send_notification("comment", project, recipients, comment.message)
                    else:
                        error = "Comment not found."
                else:
                    error = "Project not found."
                if error:
                    logger.warning(
                        f"Error trying to send new comment notification (project id={parameters[1]} comment id={parameters[2]}: {error}"
                    )

            # new status notification
            elif parameters[0] in [
                "ready-1",
                "validated-1",
                "ready",
                "validated",
                "validated-10",
                "rejected",
            ]:
                project = Project.query.filter(Project.id == int(parameters[1])).first()
                if project:
                    error = send_notification(parameters[0], project)
                else:
                    error = "Project not found."
                    logger.warning(
                        f"Error trying to send notification (project id={parameters[1]} status={parameters[0]}: {error}"
                    )
            else:
                error = "Unknown notification."

            # update action
            if error:
                action.status = "failed"
            else:
                QueuedAction.query.filter(QueuedAction.id == action.id).delete()

            # update database
            db.session.commit()

            if error:
                return jsonify({"html": "Failed!"})
            else:
                return jsonify({"html": "Done!"})

        else:
            logger.error(
                f"Error Action id={action.id} type={action.action_type} status={action.status}."
            )
            return jsonify({"html": "No pending action or known action type."})
    else:
        logger.error(f"Error: action id={action_id} not fownd.")
        return jsonify({"html": "No action found."})


# historique du projet
@main.route("/history/<int:id>", methods=["GET"])
@login_required
def history(id):
    project = Project.query.filter(Project.id == id).first()
    if project:
        if (
            current_user.id == project.uid
            or any(member.pid == current_user.pid for member in project.members)
            or current_user.p.role
            in [
                "gestion",
                "direction",
                "admin",
            ]
        ):
            # create a list of triplets (status, updated_at, updated_by)
            if project.validated_at and project.validated_at >= project.modified_at:
                project_history = [(project.status, project.validated_at, project.validated_by)]
            else:
                project_history = [(project.status, project.modified_at, project.modified_by)]

            project_history += [
                (entry.status, entry.updated_at, entry.updated_by) for entry in project.history
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
        return (
            jsonify({"Erreur": "Vous ne pouvez pas accéder à l'historique de ce projet."}),
            404,
        )
    else:
        return (
            jsonify({"Erreur": f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé."}),
            404,
        )


@main.route("/project/validation/<int:id>", methods=["GET"])
@login_required
def validate_project(id):
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(request.referrer)

    project = Project.query.filter(Project.id == id).first()
    if (
        not project
        or current_user.p.role != "direction"
        or project.status not in ["ready-1", "ready"]
    ):
        return redirect(request.referrer)

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

    # send email notification
    warning_flash = None
    if gmail_service_api:
        async_action = QueuedAction(
            uid=current_user.id,
            timestamp=get_datetime(),
            status="pending",
            action_type="send_notification",
            parameters=f"{project.status},{project.id}",
        )
        db.session.add(async_action)
    else:
        warning_flash = "API GMail non connectée : aucune notification envoyée par e-mail."

    # update database
    db.session.commit()

    message = f"Le projet <strong>{project.title}</strong> <br>"
    if project.status == "validated-1":
        if project.has_budget():
            message = f"Le budget du projet <strong>{project.title}</strong> <br>"
        message += "a été approuvé"
    else:
        message += "a été validé"
    message += " avec succès !"
    flash(message, "info")

    if warning_flash:
        flash(warning_flash, "warning")

    logger.info(f"Project id={id} ({project.title}) validated by {current_user.p.email}")

    return redirect(request.referrer)


@main.route("/project/devalidation/<int:id>", methods=["GET"])
@login_required
def devalidate_project(id):
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(request.referrer)

    project = Project.query.filter(Project.id == id).first()
    if not project or current_user.p.role != "direction" or project.status != "validated":
        return redirect(request.referrer)

    # add new record history
    history_entry = ProjectHistory(
        project_id=project.id,
        updated_at=project.validated_at,
        updated_by=project.validated_by,
        status=project.status,
    )
    db.session.add(history_entry)

    # update project
    date = get_datetime()
    project.validated_at = date
    project.validated_by = current_user.id
    project.status = "validated-10"

    # send email notification
    warning_flash = None
    if gmail_service_api:
        async_action = QueuedAction(
            uid=current_user.id,
            timestamp=get_datetime(),
            status="pending",
            action_type="send_notification",
            parameters=f"{project.status},{project.id}",
        )
        db.session.add(async_action)
    else:
        warning_flash = "API GMail non connectée : aucune notification envoyée par e-mail."

    # update database
    db.session.commit()

    flash(f"Le projet <strong>{project.title}</strong> <br>a été dévalidé avec succès.", "info")

    if warning_flash:
        flash(warning_flash, "warning")

    logger.info(f"Project id={id} ({project.title}) devalidated by {current_user.p.email}")

    return redirect(request.referrer)


@main.route("/project/reject/<int:id>", methods=["GET"])
@login_required
def reject_project(id):
    # get database status
    lock = Dashboard.query.first().lock

    # check if database is open
    if lock:
        flash("La modification des projets n'est plus possible.", "danger")
        return redirect(request.referrer)

    project = Project.query.filter(Project.id == id).first()
    if (
        not project
        or current_user.p.role != "direction"
        or project.status not in ["ready-1", "ready"]
    ):
        return redirect(request.referrer)

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
    project.status = "rejected"

    # send email notification
    warning_flash = None
    if gmail_service_api:
        async_action = QueuedAction(
            uid=current_user.id,
            timestamp=get_datetime(),
            status="pending",
            action_type="send_notification",
            parameters=f"{project.status},{project.id}",
        )
        db.session.add(async_action)
    else:
        warning_flash = "API GMail non connectée : aucune notification envoyée par e-mail."

    # update database
    db.session.commit()

    message = f"Le projet <strong>{project.title}</strong> <br>a été refusé avec succès."
    flash(message, "info")

    if warning_flash:
        flash(warning_flash, "warning")

    logger.info(f"Project id={id} ({project.title}) rejected by {current_user.p.email}")

    return redirect(request.referrer)


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
        return redirect(request.referrer)

    project = Project.query.filter(Project.id == id).first()
    if project:
        if current_user.id == project.uid and project.status != "validated":
            title = project.title
            try:
                # update school years
                school_year = SchoolYear.query.filter(SchoolYear.sy == project.school_year).first()
                school_year.nb_projects -= 1
                # delete the school year if no projects and not the current one
                if project.school_year != sy and school_year.nb_projects == 0:
                    db.session.delete(school_year)

                # delete project
                db.session.delete(project)

                # update database
                db.session.commit()

                # save_projects_df(data_path, projects_file)
                flash(f"Le projet <strong>{title}</strong> <br>a été supprimé avec succès.", "info")
                logger.info(f"Project id={id} ({title}) deleted by {current_user.p.email}")
            except Exception as e:
                db.session.rollback()
                logger.error(
                    f"Error deleting project id={id} ({title}) by {current_user.p.email}. Error: {e}"
                )
                flash(
                    f"Erreur : suppression impossible du projet <strong>{title}</strong>.", "danger"
                )
        else:
            flash("Vous ne pouvez pas supprimer ce projet.", "danger")
    else:
        flash(f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.", "danger")

    return redirect(url_for("projects.list_projects"))


# fiche projet avec commentaires
@main.route("/project/<int:id>", methods=["GET"])
@login_required
def project(id):
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    project = Project.query.filter(Project.id == id).first()

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

            # queued action
            queued_action = QueuedAction.query.filter(
                QueuedAction.uid == current_user.id, QueuedAction.status == "pending"
            ).first()
            action_id = queued_action.id if queued_action else None

            return render_template(
                "project.html",
                project=p,
                dfc=dfc,
                sy_start=sy_start,
                sy_end=sy_end,
                sy=sy,
                form=form,
                lock=lock,
                action_id=action_id,
            )
        else:
            flash("Vous ne pouvez pas accéder à cette fiche projet.", "danger")
    else:
        flash(f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé.", "danger")

    return redirect(url_for("projects.list_projects"))


@main.route("/project/comment/add", methods=["POST"])
@login_required
def project_add_comment():
    # get database status
    lock = Dashboard.query.first().lock

    form = CommentForm()

    # check if database is open
    if lock == 2:
        flash("La base fermée. Il n'est plus possible d'ajouter un commentaire.", "danger")
        if form.validate_on_submit():
            id = form.project.data
            return redirect(url_for("main.project", id=id))
        return redirect(url_for("projects.list_projects"))

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.filter(Project.id == id).first()

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
            warning_flash = None
            if form.recipients.data:
                recipients = form.recipients.data.split(",")
                # update user table: set new_message notification
                for pid in recipients:
                    user = Personnel.query.filter(Personnel.id == pid).first().user
                    if user:
                        if user.new_messages:
                            user.new_messages += f",{str(project.id)}"
                        else:
                            user.new_messages = str(project.id)
                        db.session.flush()

                # send email notification
                if gmail_service_api:
                    async_action = QueuedAction(
                        uid=current_user.id,
                        timestamp=get_datetime(),
                        status="pending",
                        action_type="send_notification",
                        parameters=f"comment,{project.id},{comment.id}",
                        options=form.recipients.data,
                    )
                    db.session.add(async_action)
                    db.session.flush()
                else:
                    warning_flash = (
                        "API GMail non connectée : aucune notification envoyée par e-mail."
                    )
            else:
                warning_flash = (
                    "Attention : aucune notification n'a pu être envoyée (aucun destinataire)."
                )

            # update database
            db.session.commit()

            flash("Nouveau message enregistré avec succès !", "info")

            if warning_flash:
                flash(warning_flash, "warning")

            return redirect(url_for("main.project", id=id))
        else:
            flash("Vous ne pouvez pas commenter ce projet.", "danger")

    return redirect(url_for("projects.list_projects"))


@main.route("/project/print/<int:id>", methods=["GET"])
@login_required
def print_fieldtrip_pdf(id):
    # get project
    project = Project.query.filter(Project.id == id).first()

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
        return redirect(url_for("projects.list_projects"))

    if not matplotlib_module:
        flash(
            "Ressources serveur insuffisantes pour générer la fiche de sortie scolaire.",
            "danger",
        )
        return redirect(request.referrer)

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
    form3 = SelectYearsForm()
    form3.years.choices = get_years_choices()
    schoolyears = len(form3.years.choices) > 1

    # default to current school year if not in session
    if "sy" not in session:
        session["sy"] = sy

    # school year selection
    if form3.validate_on_submit():
        if form3.years.data == "Toutes les années":
            session["sy"] = None
        else:
            session["sy"] = form3.years.data

    form3.years.data = session["sy"]

    if request.method == "GET":
        # return a "working..." waiting page
        # form POST request on page load
        return render_template(
            "data.html",
            form3=form3,
            schoolyears=schoolyears,
            data_html=None,
        )

    # generate data analysis
    data_html = data_analysis(session["sy"])

    return render_template(
        "data.html",
        form3=form3,
        schoolyears=schoolyears,
        data_html=data_html,
    )


@main.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    # check for authorized user
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("projects.list_projects"))

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


@main.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("projects.list_projects"))

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
            dash.lock = lock
            db.session.commit()
        else:
            flash(
                "Attention : la base est momentanément fermée pour maintenance, <br>les modifications sont impossibles.",
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
        app_version=app_version,
    )


@main.route("/download", methods=["POST"])
@login_required
def download():
    form = DownloadForm()
    form.sy.choices, form.fy.choices = get_years_choices(fy=True)

    if form.validate_on_submit():
        if current_user.p.role in ["gestion", "direction", "admin"]:
            years = form.sy.data if form.selection_mode.data == "sy" else form.fy.data
            df = get_projects_df(years=years, data="Excel", labels=True)
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


@main.route("/dashboard/personnels", methods=["GET", "POST"])
@login_required
def dashboard_personnels():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("projects.list_projects"))

    personnels = Personnel.query.order_by(
        case(
            {role: index for index, role in enumerate(choices["role"])},
            value=Personnel.role,
            else_=len(choices["role"]),  # this will place empty roles at the end
        ),
        Personnel.name,
    ).all()

    return render_template("personnels.html", personnels=personnels, choices=choices)


@main.route("/dashboard/sy", methods=["GET", "POST"])
@login_required
def dashboard_sy():
    if current_user.p.role not in ["gestion", "direction", "admin"]:
        return redirect(url_for("projects.list_projects"))

    # db lock check
    dash = Dashboard.query.first()
    if dash and current_user.p.role != "admin" and dash.lock == 2:
        flash(
            "Attention : la base est momentanément fermée pour maintenance, <br>les modifications sont impossibles.",
            "danger",
        )
        return redirect(url_for("main.dashboard"))

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

        return redirect(url_for("main.dashboard"))

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


@main.route("/profile", methods=["GET"])
@login_required
def profile():
    return render_template(
        "profile.html",
    )


@main.route("/help", methods=["GET"])
@login_required
def help():
    return render_template(
        "help.html",
    )


@main.route("/language/<language>")
def set_language(language="fr"):
    response = make_response(redirect(request.referrer or "/"))
    response.set_cookie("lang", language)
    return response
