# routes/projects.py
from flask import (
    Blueprint,
    current_app,
    session,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    send_file,
    jsonify,
)
from flask_login import login_required, current_user

from datetime import datetime, time

import os
import re

from ..models import (
    db,
    Personnel,
    Project,
    ProjectMember,
    ProjectHistory,
    ProjectComment,
    Dashboard,
    SchoolYear,
    QueuedAction,
)
from ..project import (
    ProjectForm,
    CommentForm,
    SelectProjectForm,
    ProjectFilterForm,
    SelectYearsForm,
    choices,
    valid_division,
)

from ..decorators import require_unlocked_db
from ..communication import queue_status_notification, queue_comment_notification
from ..notifications import send_notification
from ..utils import (
    get_datetime,
    auto_dashboard,
    auto_school_year,
    get_years_choices,
    get_name,
    get_axis,
    get_school_year_choices,
    get_member_choices,
    get_divisions_choices,
    get_divisions_ux_choices,
    get_status_choices,
    get_calendar_constraints,
    get_divisions,
    division_name,
    get_comments_df,
    get_comment_recipients,
    get_projects_df,
    update_database,
)

from ..data import data_analysis

import logging

logger = logging.getLogger(__name__)


try:
    from ..print import prepare_field_trip_data, generate_fieldtrip_pdf

    matplotlib_module = True
except ImportError:
    matplotlib_module = False

projects_bp = Blueprint("projects", __name__)

# basefilename to save projects data (pickle format)
projects_file = "projets"

# field trip PDF form filename
fieldtrip_pdf = "formulaire_sortie-<id>.pdf"


# asynchronous actions
@projects_bp.route("/action/<int:action_id>", methods=["GET"])
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


@projects_bp.route("/projects", methods=["GET", "POST"])
@login_required
def list_projects():
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
        df = get_projects_df(
            current_user.p.department, years=session["sy"], current_user_uid=current_user.id
        )
        df = df[
            df["members"].apply(lambda x: str(current_user.pid) in x.split(","))
            | (df["uid"] == current_user.id)
        ]
        if session["filter"] == "Mes projets à valider":
            df = df[(df.status == "ready-1") | (df.status == "ready")]
    elif current_user.p.role in ["gestion", "direction", "admin"]:
        if session["filter"] in ["LFS", "Projets à valider"]:
            df = get_projects_df(years=session["sy"], current_user_uid=current_user.id)
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            df = get_projects_df(
                session["filter"], years=session["sy"], current_user_uid=current_user.id
            )
    else:
        if session["filter"] in [current_user.p.department, "Projets à valider"]:
            df = get_projects_df(
                current_user.p.department, years=session["sy"], current_user_uid=current_user.id
            )
            if session["filter"] == "Projets à valider":
                df = df[(df.status == "ready-1") | (df.status == "ready")]
        else:
            if session["filter"] == "LFS":
                df = get_projects_df(
                    years=session["sy"], draft=False, current_user_uid=current_user.id
                )
            else:
                df = get_projects_df(
                    session["filter"],
                    years=session["sy"],
                    draft=False,
                    labels=True,
                    current_user_uid=current_user.id,
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


@projects_bp.route("/form", methods=["GET"])
@projects_bp.route("/form/<int:id>/<req>", methods=["GET"])
@login_required
@require_unlocked_db(level=1)
def project_form(id=None, req=None):
    # get database status
    lock = Dashboard.query.first().lock

    # get school year
    sy_start, sy_end, sy = auto_school_year()
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

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


@projects_bp.route("/form", methods=["POST"])
@login_required
@require_unlocked_db(level=1)
def project_form_post():
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock

    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # set current and next school year labels
    sy_current = sy
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

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
        if project.status.startswith("ready") and project.status != previous_status:
            warning_flash = queue_status_notification(project, current_user.id)
        else:
            warning_flash = None

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


@projects_bp.route("/project/validation/<int:id>", methods=["GET"])
@login_required
@require_unlocked_db(level=1)
def validate_project(id):
    project = Project.query.get_or_404(id)

    if current_user.p.role != "direction" or project.status not in ["ready-1", "ready"]:
        return redirect(request.referrer)

    db.session.add(
        ProjectHistory(
            project_id=project.id,
            updated_at=project.modified_at,
            updated_by=project.modified_by,
            status=project.status,
        )
    )

    project.validated_at = get_datetime()
    project.validated_by = current_user.id
    project.status = "validated-1" if project.status == "ready-1" else "validated"

    # send email notification
    warning_flash = queue_status_notification(project, current_user.id)

    db.session.commit()

    flash(f"Le projet <strong>{project.title}</strong> a été approuvé avec succès !", "info")
    if warning_flash:
        flash(warning_flash, "warning")

    return redirect(request.referrer)


@projects_bp.route("/project/devalidation/<int:id>", methods=["GET"])
@login_required
@require_unlocked_db(level=1)
def devalidate_project(id):
    project = Project.query.get_or_404(id)
    if current_user.p.role != "direction" or project.status != "validated":
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
    warning_flash = queue_status_notification(project, current_user.id)

    # update database
    db.session.commit()

    flash(f"Le projet <strong>{project.title}</strong> <br>a été dévalidé avec succès.", "info")

    if warning_flash:
        flash(warning_flash, "warning")

    logger.info(f"Project id={id} ({project.title}) devalidated by {current_user.p.email}")

    return redirect(request.referrer)


@projects_bp.route("/project/reject/<int:id>", methods=["GET"])
@login_required
@require_unlocked_db(level=1)
def reject_project(id):
    project = Project.query.get_or_404(id)
    if current_user.p.role != "direction" or project.status not in ["ready-1", "ready"]:
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
    warning_flash = queue_status_notification(project, current_user.id)

    # update database
    db.session.commit()

    message = f"Le projet <strong>{project.title}</strong> <br>a été refusé avec succès."
    flash(message, "info")

    if warning_flash:
        flash(warning_flash, "warning")

    logger.info(f"Project id={id} ({project.title}) rejected by {current_user.p.email}")

    return redirect(request.referrer)


@projects_bp.route("/project/delete/<int:id>", methods=["GET"])
@login_required
@require_unlocked_db(level=1)
def delete_project(id):
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    project = Project.query.get_or_404(id)
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
@projects_bp.route("/project/<int:id>", methods=["GET"])
@login_required
def project(id):
    dash = Dashboard.query.first()
    # get database status
    lock = dash.lock
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    project = Project.query.get_or_404(id)

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
            df = get_projects_df(filter=id, current_user_uid=current_user.id)

            # get project row as named tuple
            p = next(df.itertuples())

            # get project comments DataFrame
            dfc = get_comments_df(id)

            # get e-mail notification recipients
            recipients = get_comment_recipients(project, current_user.pid)

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


@projects_bp.route("/project/comment/add", methods=["POST"])
@login_required
@require_unlocked_db(level=2)
def project_add_comment():
    # get database status
    lock = Dashboard.query.first().lock

    form = CommentForm()

    # check if database is open
    if lock == 2:
        flash("La base fermée. Il n'est plus possible d'ajouter un commentaire.", "danger")
        if form.validate_on_submit():
            id = form.project.data
            return redirect(url_for("projects.project", id=id))
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
                warning_flash = queue_comment_notification(
                    project.id, comment.id, current_user.id, form.recipients.data
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

            return redirect(url_for("projects.project", id=id))
        else:
            flash("Vous ne pouvez pas commenter ce projet.", "danger")

    return redirect(url_for("projects.list_projects"))


# historique du projet
@projects_bp.route("/history/<int:id>", methods=["GET"])
@login_required
def history(id):
    project = Project.query.get_or_404(id)
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


@projects_bp.route("/project/print/<int:id>", methods=["GET"])
@login_required
def print_fieldtrip_pdf(id):
    # get project
    project = Project.query.get_or_404(id)

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
    data_path = current_app.config["DATA_PATH"]
    filename = fieldtrip_pdf.replace("<id>", str(id))
    pdf_filepath = data_path / filename

    # generate PDF if file does not exists
    if current_user.p.role in [
        "gestion",
        "direction",
        "admin",
    ] or not os.path.exists(pdf_filepath):
        # prepare data
        data = prepare_field_trip_data(project)
        # generate PDF document
        is_prod = current_app.config.get("FLASK_ENV") == "production"
        generate_fieldtrip_pdf(data, pdf_filepath, is_prod, data_path)

    return send_file(pdf_filepath, as_attachment=False)


@projects_bp.route("/data", methods=["GET", "POST"])
@login_required
def data():
    # get school year
    sy_start, sy_end, sy = auto_school_year()

    # get school year choices
    form3 = SelectYearsForm()
    form3.years.choices = get_years_choices()
    schoolyears_to_choose_from = len(form3.years.choices) > 1

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

    # Get the number of school years (None for "Toutes les années")
    # This is used for the data page title
    if form3.years.data:
        years = form3.years.data.split(" - ")
        schoolyears = int(years[1]) - int(years[0])
    else:
        schoolyears = None

    if request.method == "GET":
        # return a "working..." waiting page
        # form POST request on page load
        return render_template(
            "data.html",
            form3=form3,
            schoolyears=schoolyears,
            schoolyears_to_choose_from=schoolyears_to_choose_from,
            data_html=None,
        )

    # generate data analysis
    data_html = data_analysis(session["sy"])

    return render_template(
        "data.html",
        form3=form3,
        schoolyears=schoolyears,
        schoolyears_to_choose_from=schoolyears_to_choose_from,
        data_html=data_html,
    )
