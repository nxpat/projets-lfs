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
from .models import Personnel, Project, Comment, Dashboard
from . import db

from .projects import (
    ProjectForm,
    CommentForm,
    SelectProjectForm,
    LockForm,
    ProjectFilterForm,
    DownloadForm,
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

from email.utils import formataddr
from .gmail_api_client import gmail_send_message


# init logger
logger = logging.getLogger(__name__)

main = Blueprint("main", __name__)

# data directory
data_dir = "data"

# the path to access the data directory
path = "project"  # development
# path = "projets-lfs/project"  # PythonAnywhere

# basefilename to save projects data (pickle format)
projects_file = "projets"

# app website
website = "https://nxp.pythonanywhere.com/"


def format_addr(emails):
    f_email = []
    for email in emails:
        personnel = Personnel.query.get(email)
        f_email.append(formataddr((f"{personnel.firstname} {personnel.name}", email)))
    return ",".join(f_email)


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_projects_df(department="", id=None):
    """Convert Project table to DataFrame"""
    if Project.query.count() != 0:
        if department != "":
            projects = [
                p.__dict__
                for p in Project.query.filter(
                    Project.departments.contains(department)
                ).all()
            ]
        elif id != None:
            projects = [Project.query.get(id).__dict__]
        else:
            projects = [p.__dict__ for p in Project.query.all()]
        for p in projects:
            p.pop("_sa_instance_state", None)
        # set Id column as index
        df = pd.DataFrame(projects, columns=Project.__table__.columns.keys()).set_index(
            ["id"]
        )
    else:
        df = pd.DataFrame(columns=Project.__table__.columns.keys())
    return df


def get_comments_df(project):
    """Convert Comment table to DataFrame"""
    if Comment.query.count() != 0:
        comments = [
            c.__dict__ for c in Comment.query.filter(Comment.project == project).all()
        ]
        for c in comments:
            c.pop("_sa_instance_state", None)
        # set Id column as index
        df = pd.DataFrame(
            comments, columns=["id", "email", "message", "posted"]
        ).set_index(["id"])
    else:
        df = pd.DataFrame(columns=["id", "email", "message", "posted"])
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
    def get_date_fr(date, time=False):
        if time:
            return format_datetime(
                date, format="EEE d MMM yyyy H:mm", locale="fr_FR"
            ).capitalize()
        else:
            return format_date(
                date, format="EEE d MMM yyyy", locale="fr_FR"
            ).capitalize()

    def get_created(date, user_email, project_email):
        if user_email == project_email:
            return f"{get_date_fr(date)} par moi"
        else:
            return f"{get_date_fr(date)} par {get_name(project_email)}"

    def get_name(email, name=0):
        personnel = Personnel.query.get(email)
        if name == 1:
            return f"{personnel.firstname}"
        elif name == 2:
            return f"{personnel.name}"
        else:
            return f"{personnel.firstname} {personnel.name}"

    def get_project_dates(date_1, date_2):
        if type(date_2) is pd.Timestamp:
            return f"Du {get_date_fr(date_1)}<br>au {get_date_fr(date_2)}"
        else:
            return get_date_fr(date_1)

    def krw(v):
        return f"{v:,} KRW".replace(",", " ")

    def is_nat(val):
        return pd.isnull(val)

    return dict(
        get_date_fr=get_date_fr,
        get_created=get_created,
        get_name=get_name,
        get_project_dates=get_project_dates,
        krw=krw,
        is_nat=is_nat,
    )


@main.route("/")
def index():
    if current_user.is_authenticated and (
        current_user.role in ["admin", "gestion", "direction"]
    ):
        return redirect(url_for("main.dashboard"))
    else:
        return render_template("index.html")


@main.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    lock = Dashboard.query.get(1).lock

    n_projects = Project.query.count()

    form = LockForm(request.form, lock="Fermé" if lock else "Ouvert")

    if form.validate_on_submit():
        setattr(
            Dashboard.query.get(1),
            "lock",
            False if form.lock.data == "Ouvert" else True,
        )
        db.session.commit()
        lock = Dashboard.query.get(1).lock

    return render_template(
        "dashboard.html",
        form=form,
        form2=DownloadForm(),
        n_projects=n_projects,
        lock=lock,
    )


@main.route("/project", methods=["GET", "POST"])
@login_required
def project():
    # get database status
    lock = Dashboard.query.get(1).lock

    form = ProjectForm()

    if "project" in session:
        id = session["project"]
    else:
        id = None

    if request.method == "GET":
        if "project" in session:
            project = Project.query.get(id)
            data = {}
            for f in form.data:
                if f in Project.__table__.columns.keys():
                    if f in ["departments", "teachers", "divisions", "paths", "skills"]:
                        data[f] = getattr(project, f).split(",")
                    else:
                        data[f] = getattr(project, f)
            form = ProjectForm(data=data)
            form.priority.choices = [
                p
                for p in choices["priorities"][
                    [axe[0] for axe in choices["axes"]].index(project.axis)
                ]
            ]
            if project.validation:
                flash(
                    f"Ce projet a déjà été validé. Toute modification entraînera un nouveau processus de validation.",
                    "warning",
                )
        else:
            form = ProjectForm(
                data={
                    "departments": [current_user.department],
                    "teachers": [current_user.email],
                }
            )

    # SelectMultipleField with dynamic choice values
    choices["teachers"] = [
        (personnel.email, f"{personnel.name} {personnel.firstname}")
        for personnel in Personnel.query.filter(
            Personnel.department != "Administration"
        ).all()
    ]
    form.teachers.choices = choices["teachers"]

    # validate form
    if form.validate_on_submit():
        date = get_datetime()

        if "project" in session:
            project = Project.query.get(id)
            project.modified = date
            project.comments = project.comments.rstrip("Nn")
            if not pd.isnull(project.validation):
                message = f"Bonjour,\n\nLe projet \"{project.title}\" validé le {project.validation.strftime('%d-%m-%Y')} vient d'être modifié. Le projet n'est plus validé."
                message += "\n\nVous pouvez consulter la fiche du projet et le valider de nouveau en vous connectant à l'application Projets LFS : "
                message += website
                sender = [
                    Personnel.query.filter(Personnel.role == "admin").first().email
                ]
                recipients = [
                    personnel.email
                    for personnel in Personnel.query.filter(
                        Personnel.role.in_(["gestion", "direction"])
                    ).all()
                ]
                gmail_send_message(
                    format_addr(sender),
                    format_addr(recipients),
                    message,
                    subject=f"Projet validé modifié : {project.title}",
                )

            project.validation = None
        else:
            project = Project(
                email=current_user.email,
                created=date,
                modified=date,
                validation=None,
                comments="0",
                auth=False,
            )

        for f in form.data:
            if f in Project.__table__.columns.keys():
                if f in ["teachers", "divisions", "paths", "skills"]:
                    setattr(project, f, ",".join(form.data[f]))
                elif f == "website":
                    setattr(project, f, re.sub(r"^https?://", "", form.data[f]))
                else:
                    setattr(project, f, form.data[f])

        departments = {
            Personnel.query.get(teacher).department for teacher in form.teachers.data
        }
        setattr(project, "departments", ",".join(departments))

        if "project" in session and (not lock or project.auth):
            session.pop("project")
            if (
                current_user.email in Project.query.get(id).teachers
                or current_user.role == "admin"
            ):
                db.session.commit()
                # save_projects_df(path, projects_file)
                flash(
                    f'Le projet "{project.title}" a été modifié avec succès !',
                    "info",
                )
                logger.info(f"Project id={id} modified by {current_user.email}")
            else:
                flash("Vous ne pouvez pas modifier ce projet.")
        elif not lock:
            db.session.add(project)
            db.session.commit()
            # save pickle when a new project is added
            save_projects_df(path, projects_file)
            logger.info(f"New project added ({project.title}) by {current_user.email}")
        else:
            flash("L'enregistrement des projets n'est plus possible.")

        id = None
        return redirect(url_for("main.projects"))

    return render_template(
        "project.html",
        form=form,
        id=id,
        choices=choices,
        lock=lock,
    )


@main.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    # create locker record if Dashboard is empty
    # default to database opened
    if Dashboard.query.first() is None:
        dash = Dashboard(lock=False)
        db.session.add(dash)
        db.session.commit()

    # get database status
    lock = Dashboard.query.get(1).lock

    if "project" in session:
        session.pop("project")

    form2 = ProjectFilterForm()

    if form2.validate_on_submit():
        if current_user.role in ["gestion", "direction", "admin"]:
            session["filter"] = form2.filter.data

    # convert Project table to DataFrame
    if current_user.role in ["gestion", "direction", "admin"]:
        if "filter" not in session:
            session["filter"] = "LFS"  # default
        if session["filter"] in ["LFS", "Projets à valider"]:
            df = get_projects_df()
            if session["filter"] == "Projets à valider":
                df = df[pd.isnull(df.validation)]
        else:
            df = get_projects_df(session["filter"])
    else:
        df = get_projects_df(current_user.department)

    # set axes and priorities labels
    df["axis"] = df["axis"].map(axes)
    df["priority"] = df["priority"].map(priorities)

    # to-do notification
    new = "n" if current_user.role in ["gestion", "direction"] else "N"
    m = len(df[df.comments.str.contains(new)])
    p = len(df[pd.isnull(df.validation)])
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


@main.route("/project/print", methods=["POST"])
@login_required
def print_project():
    form = SelectProjectForm()

    url = request.referrer

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)

        if current_user.email in project.teachers or current_user.role in [
            "gestion",
            "direction",
            "admin",
        ]:
            # get project data as DataFrame
            df = get_projects_df(id=id)

            # set axes and priorities labels
            df["axis"] = df["axis"].map(axes)
            df["priority"] = df["priority"].map(priorities)

            # get project row as named tuple
            p = next(df.itertuples())

            return render_template("print.html", project=p)

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
            if current_user.email == project.email or current_user.role == "admin":
                title = project.title
                db.session.delete(project)
                db.session.commit()
                # save_projects_df(path, projects_file)
                flash(f'Le projet "{title}" a été supprimé.', "info")
                logger.info(
                    f"Project id={id} ({title}) deleted by {current_user.email}"
                )
            else:
                flash("Vous ne pouvez pas supprimer ce projet.")
        else:
            flash("La suppression des projets n'est plus possible.")

    return redirect(url_for("main.projects"))


@main.route("/project/update", methods=["POST"])
@login_required
def update_project():
    # get database status
    lock = Dashboard.query.get(1).lock

    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)
        if not lock or project.auth:
            if current_user.email in project.teachers or current_user.role == "admin":
                session["project"] = id
                return redirect(url_for("main.project"))
            else:
                flash("Vous ne pouvez pas modifier ce projet.")
        else:
            flash("La modification des projets n'est plus possible.")

    return redirect(url_for("main.projects"))


@main.route("/data", methods=["GET", "POST"])
@login_required
def data():
    # SelectMultipleField with dynamic choice values
    choices["teachers"] = [
        (personnel.email, f"{personnel.name} {personnel.firstname}")
        for personnel in Personnel.query.filter(
            Personnel.department != "Administration"
        ).all()
    ]

    # convert Project table to DataFrame
    if current_user.role in ["gestion", "direction", "admin"]:
        df = get_projects_df()
    else:
        df = get_projects_df(current_user.department)

    # calculate the distribution of projects (number and pecentage)
    dist = {}

    # total number of projects
    dist["TOTAL"] = len(df)
    N = dist["TOTAL"]

    for axis in choices["axes"]:
        n = len(df[df.axis == axis[0]])
        dist[axis[0]] = (n, f"{N and n/N*100 or 0:.0f}%")  # 0 if division by zero
        for priority in choices["priorities"][choices["axes"].index(axis)]:
            p = len(df[df.priority == priority[0]])
            dist[priority[0]] = (p, f"{n and p/n*100 or 0:.0f}%")

    for department in choices["departments"]:
        d = len(df[df.departments.str.contains(department)])
        dist[department] = (d, f"{N and d/N*100 or 0:.0f}%")

    for teacher in choices["teachers"]:
        d = len(df[df.teachers.str.contains(teacher[0])])
        dist[teacher[0]] = (d, f"{N and d/N*100 or 0:.0f}%")

    choices["paths"] = ProjectForm().paths.choices
    for path in choices["paths"]:
        d = len(df[df.paths.str.contains(path)])
        dist[path] = (d, f"{N and d/N*100 or 0:.0f}%")

    choices["skills"] = ProjectForm().skills.choices
    for skill in choices["skills"]:
        d = len(df[df.skills.str.contains(skill)])
        dist[skill] = (d, f"{N and d/N*100 or 0:.0f}%")

    for division in choices["secondaire"]:
        d = len(df[df.divisions.str.contains(division)])
        dist[division] = (d, f"{N and d/N*100 or 0:.0f}%")

    for division in choices["primaire"] + choices["maternelle"]:
        d = len(df[df.divisions.str.contains(division)])
        dist[division] = (d, f"{N and d/N*100 or 0:.0f}%")

    choices["mode"] = ProjectForm().mode.choices
    for m in choices["mode"]:
        d = len(df[df["mode"] == m])
        dist[m] = (d, f"{N and d/N*100 or 0:.0f}%")

    choices["requirement"] = ProjectForm().requirement.choices
    for r in choices["requirement"]:
        d = len(df[df.requirement == r])
        dist[r] = (d, f"{N and d/N*100 or 0:.0f}%")

    choices["location"] = ProjectForm().location.choices
    for loc in choices["location"]:
        d = len(df[df.location == loc])
        dist[loc] = (d, f"{N and d/N*100 or 0:.0f}%")

    return render_template(
        "data.html",
        choices=choices,
        df=df,
        dist=dist,
    )


@main.route("/download", methods=["POST"])
@login_required
def download():
    form = DownloadForm()

    if form.validate_on_submit():
        if current_user.role in ["admin", "gestion"]:
            df = get_projects_df()
            if not df.empty:
                date = get_datetime().strftime("%Y-%m-%d-%Hh%M")
                filename = f"Projets_LFS-{date}.xlsx"
                filepath = os.fspath(PurePath(path, data_dir, filename))
                df.to_excel(
                    filepath,
                    sheet_name="Projets pédagogiques LFS",
                    columns=df.columns,
                )

                filepath = os.fspath(PurePath(data_dir, filename))
                return send_file(filepath, as_attachment=True)


@main.route("/project/validation", methods=["POST"])
@login_required
def project_validation():
    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)
        if current_user.role in ["direction"]:
            project.validation = get_datetime()
            project.auth = False
            db.session.commit()
            # save_projects_df(path, projects_file)

            title = project.title
            flash(f'Le projet "{title}" a été validé.', "info")
            logger.info(f"Project id={id} ({title}) validated by {current_user.email}")

    return redirect(url_for("main.projects"))


@main.route("/project/comments", methods=["POST"])
@login_required
def project_comments():
    form = SelectProjectForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)

        # remove new comment badge
        if (current_user.email in project.teachers and "N" in project.comments) or (
            current_user.role in ["gestion", "direction"] and "n" in project.comments
        ):
            project.comments = project.comments.rstrip("Nn")
            db.session.commit()
            # save_projects_df(path, projects_file)  # bug later reading db

        if current_user.email in project.teachers or current_user.role in [
            "gestion",
            "direction",
        ]:
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
                "comments.html",
                project=p,
                df=dfc,
                form=CommentForm(),
            )
        else:
            flash("Vous ne pouvez pas commenter ce projet.")

    return redirect(url_for("main.projects"))


@main.route("/project/comment/add", methods=["POST"])
@login_required
def project_add_comment():
    form = CommentForm()

    if form.validate_on_submit():
        id = form.project.data
        project = Project.query.get(id)

        # set email recipients
        if current_user.email in project.teachers:
            recipient = (
                Comment.query.filter(
                    Comment.project == id,
                    Comment.email.not_in(project.teachers.split(",")),
                )
                .order_by(Comment.id.desc())
                .first()
            )
            if recipient == None:
                recipients = [
                    personnel.email
                    for personnel in Personnel.query.filter(
                        Personnel.role == "gestion"
                    ).all()
                ]
            else:
                recipients = [recipient.email]
        else:
            recipients = project.teachers.split(",")

        # add comment
        if current_user.email in project.teachers or current_user.role in [
            "gestion",
            "direction",
        ]:
            date = get_datetime()
            comment = Comment(
                project=id,
                email=current_user.email,
                message=form.message.data,
                posted=date,
            )
            db.session.add(comment)
            db.session.commit()

            new = "n" if current_user.email in project.teachers else "N"
            project.comments = f"{int(project.comments.rstrip('Nn'))+1}{new}"
            if new == "N":
                project.auth = True
            db.session.commit()
            # save_projects_df(path, projects_file)

            # send email to recipients
            message = "Bonjour,\n\n"
            message += f'Un nouveau commentaire sur le projet "{project.title}" a été ajouté par {current_user.firstname} {current_user.name} ({current_user.email}):\n\n'
            message += form.message.data
            message += "\n\nVous pouvez répondre et consulter la fiche projet en vous connectant à l'application Projets LFS : "
            message += website
            gmail_send_message(
                format_addr([current_user.email]),
                format_addr(recipients),
                message,
            )
            flash(
                f'Un commentaire a été ajouté au projet "{project.title}".',
                "info",
            )
        else:
            flash("Vous ne pouvez pas commenter ce projet.")

    return redirect(url_for("main.projects"))


@main.route("/language/<language>")
def set_language(language="fr"):
    response = make_response(redirect(request.referrer or "/"))
    response.set_cookie("lang", language)
    return response
