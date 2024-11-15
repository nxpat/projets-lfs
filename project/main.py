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
)

from flask_login import login_required, current_user
from .models import Personnel, Project, Comment, Dashboard, User
from . import db

from .projects import (
    ProjectForm,
    CommentForm,
    SelectProjectForm,
    LockForm,
    ProjectFilterForm,
    DownloadForm,
    SchoolYearForm,
    choices,
    axes,
    priorities,
)

from datetime import datetime
from zoneinfo import ZoneInfo
from babel.dates import format_date, format_datetime

from pathlib import PurePath
import os

import pandas as pd
import pickle
import re

import logging

from .communication import send_notification

from . import app_version, data_path

import calendar

try:
    from .graphs import sunburst_chart, bar_chart, timeline_chart

    graph_module = True
except ImportError:
    graph_module = False


# init logger
logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# data directory
data_dir = "data"

# basefilename to save projects data (pickle format)
projects_file = "projets"


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_date_fr(date, withdate=True, withtime=False):
    if not withdate:
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


def get_location(loc):
    # get the label from the value of the field choices
    return next(iter([x[1] for x in ProjectForm().location.choices if x[0] == loc]))


def get_projects_df(department=None, id=None, labels=False):
    """Convert Project table to DataFrame"""
    columns = Project.__table__.columns.keys()
    columns.remove("user_id")
    columns.append("email")
    if Project.query.count() != 0:
        if department is not None:
            projects = [
                p.__dict__
                for p in Project.query.filter(
                    Project.departments.contains(department)
                ).all()
            ]
        elif id is not None:
            projects = [Project.query.get(id).__dict__]
        else:
            projects = [p.__dict__ for p in Project.query.all()]

        for p in projects:
            p.pop("_sa_instance_state", None)
            p["email"] = User.query.get(p["user_id"]).p.email
            p.pop("user_id", None)

        # set Id column as index
        df = pd.DataFrame(projects, columns=columns).set_index(["id"])

        # replace axis and priority keys by their values
        if labels:
            df["teachers"] = df["teachers"].map(
                lambda x: ",".join([get_name(e) for e in x.split(",")])
            )
            df["axis"] = df["axis"].map(axes)
            df["priority"] = df["priority"].map(priorities)
            df["location"] = df["location"].map(get_location)

    else:
        df = pd.DataFrame(columns=columns)
    return df


def get_comments_df(id):
    """Convert Comment table to DataFrame"""
    if Comment.query.count() != 0:
        comments = [
            c.__dict__ for c in Comment.query.filter(Comment.project_id == id).all()
        ]
        for c in comments:
            c.pop("_sa_instance_state", None)
            c["email"] = User.query.get(c["user_id"]).p.email
            c.pop("project_id", None)
            c.pop("user_id", None)
        # set Id column as index
        df = pd.DataFrame(
            comments, columns=["id", "email", "message", "posted_at"]
        ).set_index(["id"])
    else:
        df = pd.DataFrame(columns=["id", "email", "message", "posted_at"])
    return df


def save_projects_df(path, projects_file):
    """Save Project table as Pickled DataFrame"""
    df = get_projects_df()

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

    def is_nat(val):
        return pd.isnull(val)

    return dict(
        get_date_fr=get_date_fr,
        get_created_at=get_created_at,
        get_name=get_name,
        get_location=get_location,
        get_project_dates=get_project_dates,
        krw=krw,
        is_nat=is_nat,
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
    form3 = SchoolYearForm(sy_start=sy_start, sy_end=sy_end, sy_auto=sy_auto)

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
    form3 = SchoolYearForm()

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
    if Dashboard.query.first() is None:
        # calculate default school year dates
        sy_start, sy_end = auto_school_year()
        # set default database lock to opened
        dash = Dashboard(lock=False, sy_start=sy_start, sy_end=sy_end, sy_auto=True)
        db.session.add(dash)
        db.session.commit()

    # get database status
    lock = Dashboard.query.get(1).lock

    if "project" in session:
        session.pop("project")

    form2 = ProjectFilterForm()

    if form2.validate_on_submit():
        if current_user.p.role in ["gestion", "direction", "admin"]:
            session["filter"] = form2.filter.data

    # convert Project table to DataFrame
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

    # set labels for choices defined as tuples
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
        if id is not None:
            project = Project.query.get(id)
            if (
                current_user.p.email not in project.teachers
                and current_user.p.role != "admin"
            ):
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

    if id is not None:
        data = {}
        for f in form.data:
            if f in Project.__table__.columns.keys():
                if f in ["departments", "teachers", "divisions", "paths", "skills"]:
                    data[f] = getattr(project, f).split(",")
                else:
                    data[f] = getattr(project, f)

        for s in ["start", "end"]:
            t = data[f"{s}_date"].time()
            data[f"{s}_time"] = t
        if data["end_date"] == data["start_date"]:
            data["end_date"] = None
            data["end_time"] = None

        form = ProjectForm(data=data)
        form.priority.choices = [
            p
            for p in choices["priorities"][
                [axe[0] for axe in choices["axes"]].index(project.axis)
            ]
        ]
    else:
        form = ProjectForm(
            data={
                "departments": [current_user.p.department],
                "teachers": [current_user.p.email],
            }
        )

    # form: set SelectMultipleField with dynamic choice values
    choices["teachers"] = sorted(
        [
            (personnel.email, f"{personnel.name} {personnel.firstname}")
            for personnel in Personnel.query.filter(
                Personnel.department != "Administration"
            ).all()
        ],
        key=lambda x: x[1],
    )
    form.teachers.choices = choices["teachers"]

    # form: set school year dates for calendar
    form.start_date.render_kw = {
        "min": sy_start.date(),
        "max": sy_end.date(),
    }
    form.end_date.render_kw = form.start_date.render_kw

    # form : set dynamic status choices
    if id is None or project.status == "draft" or project.status == "ready-1":
        form.status.choices = choices["status"][:2]
    else:
        form.status.choices = choices["status"][2:]
        form.status.data = "adjust"
        form.status.description = "Le projet sera ajusté ou soumis à validation"

    return render_template(
        "form.html",
        form=form,
        id=id,
        choices=choices,
        lock=lock,
    )


@main.route("/form", methods=["POST"])
@login_required
def project_form_post():
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
        if id is not None:
            project = Project.query.get(id)
            if (
                current_user.p.email not in project.teachers
                and current_user.p.role != "admin"
            ):
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

    # form: set SelectMultipleField with dynamic choice values
    choices["teachers"] = sorted(
        [
            (personnel.email, f"{personnel.name} {personnel.firstname}")
            for personnel in Personnel.query.filter(
                Personnel.department != "Administration"
            ).all()
        ],
        key=lambda x: x[1],
    )
    form.teachers.choices = choices["teachers"]

    if form.validate_on_submit():
        date = get_datetime()

        if id is not None:
            project.updated_at = date
            project.nb_comments = project.nb_comments.rstrip("Nn")
        else:
            project = Project(
                created_at=date,
                updated_at=date,
                validation=None,
                nb_comments="0",
            )

        for f in form.data:
            if f in Project.__table__.columns.keys():
                if f in ["teachers", "divisions", "paths", "skills"]:
                    setattr(project, f, ",".join(form.data[f]))
                elif f == "website":
                    setattr(project, f, re.sub(r"^https?://", "", form.data[f]))
                elif re.match(r"(start|end)_date", f):
                    f_t = re.sub(r"date$", "time", f)
                    if form.data[f] is not None and form.data[f_t] is not None:
                        f_start = datetime.combine(form.data[f], form.data[f_t])
                        setattr(project, f, f_start)
                    elif form.data[f] is None:
                        setattr(project, f, f_start)
                    else:
                        f_start = form.data[f]
                        setattr(project, f, f_start)
                elif f == "status":
                    if form.data[f] != "adjust":
                        setattr(project, f, form.data[f])
                else:
                    setattr(project, f, form.data[f])

        departments = {
            Personnel.query.filter_by(email=teacher).first().department
            for teacher in form.teachers.data
        }
        setattr(project, "departments", ",".join(departments))

        # database update
        if id is not None:
            db.session.commit()
            # save_projects_df(data_path, projects_file)
            session.pop("project")
            flash(
                f'Le projet "{project.title}" a été modifié avec succès !',
                "info",
            )
            logger.info(f"Project id={id} modified by {current_user.p.email}")
            # send email notification
            if project.status.startswith("ready") and form.status.data != "adjust":
                error = send_notification("ready", project)
                if error is not None:
                    flash(error, "danger")
        else:
            current_user.projects.append(project)
            db.session.add(project)
            db.session.commit()
            # save pickle when a new project is added
            save_projects_df(data_path, projects_file)
            logger.info(
                f"New project added ({project.title}) by {current_user.p.email}"
            )
            # send email notification
            if project.status.startswith("ready"):
                error = send_notification("ready", project)
                if error is not None:
                    flash(error, "danger")

        id = None
        return redirect(url_for("main.projects"))

    # form: set school year dates for calendar
    form.start_date.render_kw = {
        "min": sy_start.date(),
        "max": sy_end.date(),
    }
    form.end_date.render_kw = form.start_date.render_kw

    # form : set dynamic status choices
    if id is None or project.status == "draft" or project.status == "ready-1":
        form.status.choices = choices["status"][:2]
    else:
        form.status.choices = choices["status"][2:]
        form.status.data = "adjust"
        form.status.description = "Le projet sera ajusté ou soumis à validation"

    return render_template(
        "form.html",
        form=form,
        id=id,
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
            project.validation = get_datetime()
            if project.status == "ready-1":
                project.status = "validated-1"
            elif project.status == "ready":
                project.status = "validated"
            else:
                redirect(url_for("main.projects"))
            db.session.commit()
            # save_projects_df(data_path, projects_file)

            flash(f'Le projet "{project.title}" a été validé.', "info")

            # send email notification
            error = send_notification("validation", project)
            if error is not None:
                flash(error, "danger")

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
            if (
                current_user.p.email not in project.teachers
                and current_user.p.role != "admin"
            ):
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
                db.session.delete(project)
                db.session.commit()
                # save_projects_df(data_path, projects_file)
                flash(f'Le projet "{title}" a été supprimé.', "info")
                logger.info(
                    f"Project id={id} ({title}) deleted by {current_user.p.email}"
                )
            else:
                flash("Vous ne pouvez pas supprimer ce projet.")
        else:
            flash("La suppression des projets n'est plus possible.")

    return redirect(url_for("main.projects"))


# fiche projet avec commentaires
@main.route("/project/<int:id>", methods=["GET"])
@main.route("/project", methods=["POST"])
@login_required
def project(id=None):
    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data

    project = Project.query.get(id)

    if current_user.p.email in project.teachers or current_user.p.role in [
        "gestion",
        "direction",
    ]:
        # remove new comment badge
        if (
            current_user.p.email in project.teachers and "N" in project.nb_comments
        ) or (
            current_user.p.role in ["gestion", "direction"]
            and "n" in project.nb_comments
        ):
            project.nb_comments = project.nb_comments.rstrip("Nn")
            db.session.commit()
            # save_projects_df(data_path, projects_file)  # bug later reading db

        # get project data as DataFrame
        df = get_projects_df(id=id)

        # set axes and priorities labels
        df["axis"] = df["axis"].map(axes)
        df["priority"] = df["priority"].map(priorities)

        # get project row as named tuple
        p = next(df.itertuples())

        # get comments on project as DataFrame
        dfc = get_comments_df(id)

        return render_template(
            "project.html",
            project=p,
            df=dfc,
            form=CommentForm(),
        )
    else:
        flash("Vous ne pouvez pas accéder à cette fiche projet.")

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

            flash(
                f'Un commentaire a été ajouté au projet "{project.title}".',
                "info",
            )

            # send email notification
            error = send_notification("comment", project, form.message.data)
            if error is not None:
                flash(error, "danger")

        else:
            flash("Vous ne pouvez pas commenter ce projet.")

    return redirect(url_for("main.projects"))


@main.route("/project/print", methods=["POST"])
@login_required
def print_project():
    form = SelectProjectForm()

    filename = "formulaire_sortie.pdf"

    if form.validate_on_submit():
        filepath = os.fspath(PurePath(data_dir, filename))
        return send_file(filepath)

    return redirect(url_for("main.projects"))


@main.route("/data", methods=["GET", "POST"])
@login_required
def data():
    dash = Dashboard.query.get(1)
    # get school year
    sy_start, sy_end = dash.sy_start, dash.sy_end

    # SelectMultipleField with dynamic choice values
    choices["teachers"] = sorted(
        [
            (
                personnel.email,
                f"{personnel.name} {personnel.firstname}",
                personnel.department,
            )
            for personnel in Personnel.query.filter(
                Personnel.department != "Administration"
            ).all()
        ],
        key=lambda x: x[1],
    )

    # convert Project table to DataFrame
    # if current_user.p.role in ["gestion", "direction", "admin"]:
    #     df = get_projects_df()
    # else:
    #     df = get_projects_df(current_user.p.department)
    df = get_projects_df()
    df = df[df.status.str.startswith("validated")]

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
        d = len(df[df.departments.str.contains(department)])
        s = sum(df[df.departments.str.contains(department)]["nb_students"])
        dist[department] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    d = len(
        df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)]
    )
    s = sum(
        df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)][
            "nb_students"
        ]
    )
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
        d = len(df[df.requirement == r])
        s = sum(df[df.requirement == r]["nb_students"])
        dist[r] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    choices["location"] = ProjectForm().location.choices
    for loc in choices["location"]:
        d = len(df[df.location == loc[0]])
        s = sum(df[df.location == loc[0]]["nb_students"])
        dist[loc[0]] = (d, f"{N and d/N*100 or 0:.0f}%", s)

    # budget
    dfb = pd.DataFrame(index=choices["budget"].keys())
    for department in choices["departments"]:
        b = {}
        for budget in dfb.index:
            b[budget] = df[df.departments.str.contains(department)][budget].sum()
        dfb[department] = b

    dfb["Total"] = {budget: df[budget].sum() for budget in dfb.index}

    for teacher in choices["teachers"]:
        b = {}
        for budget in dfb.index:
            b[budget] = df[df.teachers.str.contains(teacher[0])][budget].sum()
        dfb[teacher[0]] = b

    # data for graphs
    # axes et priorités du projet d'établissement
    dfa = pd.DataFrame(
        {
            "priority": [
                p[1]
                for axis in choices["priorities"]
                for p in axis
                if dist[p[0]][0] != 0
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
    sy_end_month = (
        sy_end.month + 12 if sy_end.year == sy_start.year + 1 else sy_end.month
    )
    # months (numbers) of the school year
    syi = [m % 12 for m in range(sy_start.month, sy_end_month + 1)]
    syi = [12 if m == 0 else m for m in syi]
    # months (French names) of the school year
    sy = [
        format_date(datetime(1900, m, 1), format="MMMM", locale="fr_FR").capitalize()
        for m in syi
    ]

    dft = pd.DataFrame({f"Année scolaire {sy_start.year}-{sy_end.year}": sy})

    for project in df.itertuples():
        y = sy_start.year
        timeline = [0] * len(sy)
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
        dfb=dfb,
        dist=dist,
        graph_html=graph_html,
        graph_html2=graph_html2,
        graph_html3=graph_html3,
    )


@main.route("/data/personnels", methods=["GET", "POST"])
@login_required
def data_personnels():
    if current_user.p.role in ["gestion", "direction", "admin"]:
        return render_template(
            "personnels.html",
            Personnel=Personnel,
            User=User,
            Project=Project,
        )
    else:
        return redirect(url_for("main.projects"))


@main.route("/download", methods=["POST"])
@login_required
def download():
    form = DownloadForm()

    if form.validate_on_submit():
        if current_user.p.role in ["admin", "gestion"]:
            df = get_projects_df(labels=True)
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


@main.route("/language/<language>")
def set_language(language="fr"):
    response = make_response(redirect(request.referrer or "/"))
    response.set_cookie("lang", language)
    return response
