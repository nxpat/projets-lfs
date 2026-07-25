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

from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from datetime import datetime, time

import os
import re

from ..models import (
    db,
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
from ..project import (
    ProjectForm,
    CommentForm,
    RejectProjectForm,
    SelectProjectForm,
    ProjectFilterForm,
    SelectYearsForm,
    ActionForm,
    choices,
    valid_division,
)

from ..decorators import require_unlocked_db
from ..notifications import send_notification, queue_status_notification, process_add_comment
from ..utils import (
    get_datetime,
    auto_dashboard,
    auto_school_year,
    get_years_choices,
    get_name,
    get_axis,
    get_school_year_choices,
    get_school_years,
    get_member_choices,
    get_divisions_choices,
    get_division_sections,
    get_status_choices,
    get_calendar_constraints,
    division_name,
    get_comment_recipients,
    query_projects,
    students_to_csv,
)

from ..data import data_analysis

from ..errors import get_project_or_redirect

import logging

logger = logging.getLogger(__name__)


try:
    from ..pdf_generator import prepare_field_trip_data, generate_fieldtrip_pdf

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
            parameters = action.parameters

            # new comment notification (Standard or Rejected)
            if parameters["notification_type"] in ["comment", "rejected_comment"]:
                project = Project.query.filter(Project.id == int(parameters["project_id"])).first()
                if project:
                    comment = ProjectComment.query.filter(
                        ProjectComment.id == int(parameters["comment_id"])
                    ).first()
                    if comment:
                        recipients = action.options["recipients"]
                        error = send_notification(
                            parameters["notification_type"], project, recipients, comment.message
                        )
                    else:
                        error = "Comment not found."
                else:
                    error = "Project not found."
                if error:
                    logger.warning(
                        f"Error trying to send new comment notification (project id={parameters['project_id']} comment id={parameters['comment_id']}: {error}"
                    )

            # new status notification
            elif parameters["notification_type"] in [
                "ready-1",
                "validated-1",
                "ready",
                "validated",
                "validated-10",
                "rejected",
            ]:
                project = Project.query.filter(Project.id == int(parameters["project_id"])).first()
                if project:
                    error = send_notification(parameters["notification_type"], project)
                else:
                    error = "Project not found."
                    logger.warning(
                        f"Error trying to send notification (project id={parameters['project_id']} status={parameters['notification_type']}: {error}"
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
    dash = auto_dashboard()
    lock = dash.lock
    lock_message = dash.lock_message

    # get school year
    school_year = auto_school_year()

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
        session["sy"] = school_year.sy

    form3.years.data = session["sy"]

    # Build Project query
    query = query_projects(current_user, filter=session["filter"], years=session["sy"])

    # Get the base count before applying any search query
    base_count = query.count()

    # --- Pagination ---
    # Get the current page (defaults to 1)
    page = request.args.get("page", 1, type=int)

    # Check if the user just selected a new pagination length
    per_page_request = request.args.get("per_page")

    if per_page_request:
        if per_page_request == "all":
            session["per_page"] = "all"
        else:
            try:
                session["per_page"] = int(per_page_request)
            except ValueError:
                session["per_page"] = 20  # Fallback for invalid data

    # Retrieve the current preference (defaulting to 20)
    per_page = session.get("per_page", 20)

    # Handle "all" case: use 1 if the query is empty to avoid crashes
    actual_per_page = max(1, base_count) if per_page == "all" else per_page

    # Set client or server search
    use_client_search = base_count <= actual_per_page

    # Apply dynamic SQLAlchemy Search
    search_query = request.args.get("q", "").strip()

    if search_query and not use_client_search:
        # Outer join the relationship tables ONCE so MySQL
        # searches flat columns instead of running correlated subqueries for every row
        query = query.outerjoin(Project.members).outerjoin(ProjectMember.p)

        search_filters = []

        # Specify only the columns to search through
        searchable_columns = [
            Project.school_year,
            Project.title,
            Project.objectives,
            Project.description,
            Project.axis,
            Project.priority,
            Project.paths,
            Project.skills,
            Project.divisions,
            Project.indicators,
            Project.students,
            Project.fieldtrip_address,
            Project.fieldtrip_ext_people,
            Project.fieldtrip_impact,
        ]

        searchable_columns += [getattr(Project, f"link_t_{i}") for i in range(1, 5)]

        searchable_columns += [
            getattr(Project, f"budget_{t}_c_{i}")
            for i in range(1, 3)
            for t in ("hse", "exp", "trip", "int")
        ]

        for column in searchable_columns:
            search_filters.append(column.ilike(f"%{search_query}%"))

        search_filters.append(ProjectMember.department.ilike(f"%{search_query}%"))
        search_filters.append(Personnel.name.ilike(f"%{search_query}%"))
        search_filters.append(Personnel.firstname.ilike(f"%{search_query}%"))

        # Apply OR filter and use .distinct() so projects with multiple
        # matching members don't get duplicated in the pagination count
        if search_filters:
            query = query.filter(or_(*search_filters)).distinct()

    # Apply eager loading
    query = query.options(
        # 1-to-1: joinedload
        joinedload(Project.user).joinedload(User.p),
        joinedload(Project.modifier).joinedload(User.p),
        joinedload(Project.validator).joinedload(User.p),
        # 1-to-Many Collections: selectinload for pagination
        selectinload(Project.members).joinedload(ProjectMember.p),
        selectinload(Project.comments),
    )

    # Paginate
    pagination = query.paginate(page=page, per_page=actual_per_page, error_out=False)

    if (page > pagination.pages and pagination.pages > 0) or page < 1:
        flash("La page demandée n'existe pas.", "danger")
        # Redirect to page 1, preserving the search query if the user was searching
        return redirect(url_for(".list_projects", page=1, q=search_query or None))

    # Extract the items for the current page
    projects = pagination.items

    # ------

    if current_user.p.role not in ["gestion", "direction", "admin"]:
        form2.filter.choices = choices["filter-user"]

    # to-do notification
    user_new_messages = current_user.new_messages if current_user.new_messages else []
    if user_new_messages:
        m = len(user_new_messages)
    else:
        m = 0
    if current_user.p.role in ["gestion", "direction"]:
        p = query_projects(current_user, filter="Projets à valider").count()
    else:
        p = query_projects(current_user, filter="Mes projets à valider").count()

    if m or p:
        message = "Vous avez "
        message += (
            f"{m} message{'s' if m > 1 else ''} non lu{'s' if m > 1 else ''}" if m > 0 else ""
        )
        message += " et " if m and p else ""
        message += (
            f"{p} projet{'s' if p > 1 else ''} non validé{'s' if p > 1 else ''}" if p > 0 else ""
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
        projects=projects,
        user_new_messages=set(user_new_messages),
        pagination=pagination,
        use_client_search=use_client_search,
        sy_start=school_year.sy_start,
        sy_end=school_year.sy_end,
        sy=school_year.sy,
        lock=lock,
        lock_message=lock_message,
        form=SelectProjectForm(),
        form2=form2,
        form3=form3,
        reject_form=RejectProjectForm(),
        approve_form=ActionForm(),
        validate_form=ActionForm(),
        devalidate_form=ActionForm(),
        delete_form=ActionForm(),
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
    school_year = auto_school_year()
    sy_next = f"{school_year.sy_start.year + 1} - {school_year.sy_end.year + 1}"

    # check for valid request
    if id and req not in ["duplicate", "update"]:
        flash("Requête non valide sur un projet.", "danger")
        return redirect(url_for("projects.list_projects"))

    # check access rights to project
    if id:
        project = get_project_or_redirect(id, eagerload="m")
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
                if f == "is_recurring":
                    data[f] = "Oui" if getattr(project, f) else "Non"
                elif f == "students":
                    if getattr(project, f):
                        data[f] = students_to_csv(getattr(project, f))
                    else:
                        data[f] = None
                else:
                    data[f] = getattr(project, f)

        data["members"] = [member.pid for member in project.members]

        # duplicate project
        if req == "duplicate":
            data["id"] = None
            data["school_year"] = None
            data["uid"] = None
            data["title"] = "(Copie de) " + project.title
            data["created_at"] = None
            data["modified_at"] = None
            data["modified_by"] = None
            data["validated_at"] = None
            data["validated_by"] = None
            data["budget_id"] = None
            data["status"] = "draft"

        # separate date and time fields
        for s in ["start", "end"]:
            t = data[f"{s}_date"].time()
            data[f"{s}_time"] = t if t != time(0, 0) else None

        # set school year field
        if project.start_date.date() > school_year.sy_end:
            data["school_year"] = "next"
        else:
            data["school_year"] = "current"

        # fill the form with data
        form = ProjectForm(data=data)
    else:
        form = ProjectForm(data={"members": [current_user.p.id]})

    ## form: set dynamic field choices
    # form: set school_year choices
    form.school_year.choices = get_school_year_choices(school_year.sy, sy_next)

    # form UX+JS: set calendar constraints for project dates
    form = get_calendar_constraints(form, school_year.sy_start, school_year.sy_end)

    # form: set members choices
    form.members.choices = get_member_choices()

    # form: set divisions choices
    form.divisions.choices = get_divisions_choices(school_year.sy)

    # form UX: dictionary of divisions by section
    choices["division_sections"] = get_division_sections(form)

    # form: set status choices and descriptions
    if id:
        form = get_status_choices(form, form.status.data)
    else:
        form = get_status_choices(form)

    # form UX: project has budget ?
    has_budget = project.has_budget if id else False
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
    school_year = auto_school_year()

    # set current and next school year labels
    sy_current = school_year.sy
    sy_next = f"{school_year.sy_start.year + 1} - {school_year.sy_end.year + 1}"

    form = ProjectForm()

    # get project id
    id = form.id.data

    # check access rights to project
    if id:
        project = get_project_or_redirect(id)

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
    form.divisions.choices = get_divisions_choices(school_year.sy)

    # form: set status choices and descriptions
    form = get_status_choices(form, project.status if id else None)

    if form.validate_on_submit():
        date = get_datetime()

        # save previous project data
        previous_data = {}

        if id:  # update existing project
            # update project modification date and user
            project.modified_at = date
            project.modified_by = current_user.id

            # get project previous members
            previous_members = [member.pid for member in project.members]
        else:  # create new project
            project = Project(
                created_at=date,
                uid=current_user.id,
                modified_at=date,
                modified_by=current_user.id,
            )

            previous_members = []

        # process form data
        for f in form.data:
            if f != "id" and f in Project.__table__.columns.keys():
                form_data = getattr(form, f).data
                if re.match(r"link_[1-4]$", f):
                    if form_data:
                        if re.match(r"^https?://", form_data):
                            data = form_data.strip()
                        else:
                            data = "https://" + form_data.strip()
                elif re.match(r"(start|end)_date", f):
                    f_t = re.sub(r"date$", "time", f)
                    form_data_t = getattr(form, f_t).data

                    if form_data and form_data_t:
                        data = datetime.combine(form_data, form_data_t)
                    elif not form_data:
                        # Fallback to start_date if end_date is missing
                        s_date = getattr(form, "start_date").data
                        s_time = getattr(form, "start_time").data
                        if s_date and s_time:
                            data = datetime.combine(s_date, s_time)
                        elif s_date:
                            data = datetime.combine(s_date, datetime.min.time())
                    else:
                        data = datetime.combine(form_data, datetime.min.time())
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
                            student = [v for v in student if v]
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

                            students[i] = {
                                "division": student[0],
                                "name": student[1],
                                "firstname": student[2],
                            }

                        # sort by student name, then by division
                        students.sort(
                            key=lambda x: (
                                [d[1] for d in form.divisions.choices].index(x["division"]),
                                x["name"],
                            )
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
                    if f == "fieldtrip_ext_people":
                        data = data.replace(" et ", ",")
                elif f == "is_recurring":
                    data = True if form_data == "Oui" else False
                elif f == "status":
                    data = getattr(project, f, None) if form_data == "adjust" else form_data
                else:
                    if isinstance(form_data, str):
                        data = form_data.strip()
                    else:
                        data = form_data

                # save previous data before updating project
                if f in ProjectHistory.__table__.columns.keys():
                    previous_data[f] = getattr(project, f, None)

                # update project
                setattr(project, f, data)

        # set axis data
        setattr(project, "axis", get_axis(form.priority.data))

        # check students list consistency with nb_students and divisions fields
        if project.requirement == "no" and (project.students or project.status == "ready"):
            students = project.students
            nb_students = len(students)
            division_choices = [d[0] for d in form.divisions.choices]

            # Safe parsing
            valid_divs = {
                valid_division(student["division"], division_choices) for student in students
            }
            # Filter out None values just in case
            valid_divs = {d for d in valid_divs if d}

            divisions = sorted(
                valid_divs,
                # Fallback index to prevent ValueError if division somehow isn't in choices
                key=lambda x: division_choices.index(x) if x in division_choices else 999,
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
            if project.start_date.year == school_year.sy_end.year:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_1", 0)
                    setattr(project, "budget_" + budget + "_c_1", None)
            if project.end_date.year == school_year.sy_start.year:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_2", 0)
                    setattr(project, "budget_" + budget + "_c_2", None)
        else:
            if project.start_date.year == school_year.sy_end.year + 1:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_1", 0)
                    setattr(project, "budget_" + budget + "_c_1", None)
            if project.end_date.year == school_year.sy_start.year + 1:
                for budget in ["hse", "exp", "trip", "int"]:
                    setattr(project, "budget_" + budget + "_2", 0)
                    setattr(project, "budget_" + budget + "_c_2", None)

        for year in ["1", "2"]:
            for budget in ["hse", "exp", "trip", "int"]:
                if getattr(form, "budget_" + budget + "_" + year).data == 0:
                    setattr(project, "budget_" + budget + "_c_" + year, None)

        # add project
        if not id:  # add new project
            db.session.add(project)
            db.session.flush()

        # update project members
        members = form.members.data
        if set(previous_members) != set(members):
            if id:
                # clear existing members
                ProjectMember.query.filter_by(project_id=id).delete()

            # add new members
            members_dpt = {
                p.id: p.department for p in Personnel.query.filter(Personnel.id.in_(members)).all()
            }

            for pid in members:
                project_member = ProjectMember(
                    project_id=project.id, pid=pid, department=members_dpt[pid]
                )
                db.session.add(project_member)

        # create new record history
        history_entry = ProjectHistory(
            project_id=project.id,
            updated_at=date,
            updated_by=current_user.id,
            status=project.status,
        )
        for f in previous_data:
            project_data = getattr(project, f, None)
            if f == "status" or project_data != previous_data[f]:
                setattr(history_entry, f, project_data)
            else:
                setattr(history_entry, f, None)

        # add new history
        db.session.add(history_entry)

        # update school years if necessary
        if not id:  # new project
            if project.school_year not in get_school_years():  # next school year
                project_school_year = SchoolYear(
                    sy_start=school_year.sy_start.replace(year=school_year.sy_start.year + 1),
                    sy_end=school_year.sy_end.replace(year=school_year.sy_end.year + 1),
                    sy=sy_next,
                    divisions=school_year.divisions,
                )
                db.session.add(project_school_year)

        # send email notification if status=ready-1 or status=ready
        if project.status.startswith("ready") and project.status != previous_data["status"]:
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
            logger.info(f"New project created ({project.title}) by {current_user.p.email}")

        if warning_flash:
            flash(warning_flash, "warning")

        return redirect(url_for("projects.list_projects"))

    ## form: set dynamic field choices
    # form: set school_year choices
    form.school_year.choices = get_school_year_choices(school_year.sy, sy_next)

    # form UX+JS: set calendar constraints for project dates
    form = get_calendar_constraints(form, school_year.sy_start, school_year.sy_end)

    # form UX: dictionary of divisions by section
    choices["division_sections"] = get_division_sections(form)

    # form UX: project has budget ?
    has_budget = (
        project.has_budget
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


@projects_bp.route("/project/validate/<int:id>", methods=["POST"])
@login_required
@require_unlocked_db(level=2)
def validate_project(id):
    project = get_project_or_redirect(id)

    if current_user.p.role != "direction" or project.status not in ["ready-1", "ready"]:
        return redirect(request.referrer)

    form = ActionForm()

    if form.validate_on_submit():
        # update project
        date = get_datetime()
        project.validated_at = date
        project.validated_by = current_user.id
        project.status = "validated-1" if project.status == "ready-1" else "validated"

        # add new record history
        history_entry = ProjectHistory(
            project_id=project.id,
            updated_at=project.validated_at,
            updated_by=project.validated_by,
            status=project.status,
        )
        db.session.add(history_entry)

        # send email notification
        warning_flash = queue_status_notification(project, current_user.id)

        db.session.commit()

        flash(
            f"Le projet <strong>{project.title}</strong> <br>a été {'approuvé' if project.status == 'validated-1' else 'validé'} avec succès !",
            "info",
        )
        if warning_flash:
            flash(warning_flash, "warning")

    return redirect(request.referrer)


@projects_bp.route("/project/devalidate/<int:id>", methods=["POST"])
@login_required
@require_unlocked_db(level=2)
def devalidate_project(id):
    project = get_project_or_redirect(id)

    if current_user.p.role != "direction" or project.status != "validated":
        return redirect(request.referrer)

    form = ActionForm()

    if form.validate_on_submit():
        # update project
        date = get_datetime()
        project.validated_at = date
        project.validated_by = current_user.id
        project.status = "validated-10"

        # add new record history
        history_entry = ProjectHistory(
            project_id=project.id,
            updated_at=project.validated_at,
            updated_by=project.validated_by,
            status=project.status,
        )
        db.session.add(history_entry)

        # send email notification
        warning_flash = queue_status_notification(project, current_user.id)

        # update database
        db.session.commit()

        flash(f"Le projet <strong>{project.title}</strong> <br>a été dévalidé avec succès.", "info")

        if warning_flash:
            flash(warning_flash, "warning")

        logger.info(f"Project id={id} ({project.title}) devalidated by {current_user.p.email}")

    return redirect(request.referrer)


@projects_bp.route("/project/reject/<int:project_id>", methods=["POST"])
@login_required
@require_unlocked_db(level=2)
def reject_project(project_id):
    project = get_project_or_redirect(project_id)

    # Check authorization
    if current_user.p.role != "direction" or project.status not in ["ready-1", "ready"]:
        return redirect(request.referrer)

    form = RejectProjectForm()

    if form.validate_on_submit():
        # update project
        date = get_datetime()
        project.validated_at = date
        project.validated_by = current_user.id
        project.status = "rejected"

        # add new record history
        history_entry = ProjectHistory(
            project_id=project.id,
            updated_at=project.validated_at,
            updated_by=project.validated_by,
            status=project.status,
        )
        db.session.add(history_entry)

        if form.message.data:
            recipients = [project.uid] + [member.pid for member in project.members]
            success, flashes = process_add_comment(
                project=project,
                user=current_user,
                message=form.message.data,
                recipients=recipients,
                is_rejection=True,
            )
            for msg, category in flashes:
                flash(msg, category)
        else:
            warning_flash = queue_status_notification(project, current_user.id)
            if warning_flash:
                flash(warning_flash, "warning")

    # Commit everything: project, project history, comment
    db.session.commit()

    flash(f"Le projet <strong>{project.title}</strong> <br>a été refusé avec succès.", "info")

    logger.info(f"Project id={id} ({project.title}) rejected by {current_user.p.email}")

    return redirect(request.referrer)


@projects_bp.route("/project/delete/<int:id>", methods=["POST"])
@login_required
@require_unlocked_db(level=1)
def delete_project(id):
    project = get_project_or_redirect(id)

    # Authorization and status check
    if current_user.id != project.uid or project.status == "validated":
        flash("Vous ne pouvez pas supprimer ce projet.", "danger")
        return redirect(request.referrer)

    form = ActionForm()

    if form.validate_on_submit():
        title = project.title
        school_year = auto_school_year()

        # Update school year totals
        project_school_year = SchoolYear.query.filter_by(sy=project.school_year).first()
        if project_school_year:
            # Delete the school year if no projects remain and it's not the current active year
            if project.school_year != school_year.sy and not school_year.nb_projects:
                db.session.delete(school_year)

        # Delete the project itself
        db.session.delete(project)
        db.session.commit()

        logger.info(f"Project id={id} ({title}) deleted by {current_user.p.email}")
        flash(f"Le projet <strong>{title}</strong> <br>a été supprimé avec succès.", "info")

    return redirect(url_for("projects.list_projects"))


# fiche projet avec commentaires
@projects_bp.route("/project/<int:id>", methods=["GET"])
@login_required
def view_project(id):
    project = get_project_or_redirect(id, eagerload="p")

    # Check authorization
    is_authorized = (
        current_user.id == project.uid
        or any(member.pid == current_user.pid for member in project.members)
        or current_user.p.role in ["gestion", "direction"]
        or project.status not in ["draft"]
    )
    if not is_authorized:
        flash("Vous ne pouvez pas accéder à cette fiche projet.", "danger")
        return redirect(url_for("projects.list_projects"))

    # Notification clear
    if current_user.new_messages:
        messages_list = current_user.new_messages
        if id in messages_list:
            updated_messages_list = [i for i in messages_list if i != id]
            current_user.new_messages = updated_messages_list
            db.session.commit()

    # Get school year data
    dash = Dashboard.query.first()
    school_year = auto_school_year()

    # Get e-mail notification recipients
    recipients = get_comment_recipients(project, current_user)

    # Set comment form data
    if recipients:
        form = CommentForm(
            project_id=id, recipients=",".join([str(recipient.id) for recipient in recipients])
        )

        # Display recipients names in the message field description
        names = [get_name(recipient) for recipient in recipients]
        if len(names) == 1:
            names_string = f"{names[0]}."
        else:
            names_string = ", ".join(names[:-1]) + f" et {names[-1]}."

        form.message.description += names_string
    else:
        form = CommentForm(project_id=id, recipients=None)
        form.message.description += "personne (aucun destinataire trouvé)."

    # Queued action
    queued_action = QueuedAction.query.filter_by(uid=current_user.id, status="pending").first()

    return render_template(
        "project.html",
        project=project,
        sy_start=school_year.sy_start,
        sy_end=school_year.sy_end,
        sy=school_year.sy,
        form=form,
        reject_form=RejectProjectForm(),
        approve_form=ActionForm(),
        validate_form=ActionForm(),
        devalidate_form=ActionForm(),
        delete_form=ActionForm(),
        lock=dash.lock if dash else False,
        action_id=queued_action.id if queued_action else None,
    )


@projects_bp.route("/project/comment/add", methods=["POST"])
@login_required
@require_unlocked_db(level=2)
def project_add_comment():
    form = CommentForm()

    if form.validate_on_submit():
        project_id = form.project_id.data
        project = get_project_or_redirect(project_id)

        # recipients: safely parse the csv string into a list of integers
        raw_recipients = form.recipients.data

        if raw_recipients:
            if isinstance(raw_recipients, list):
                recipients = [int(x) for x in raw_recipients if str(x).isdigit()]
            else:
                recipients = [
                    int(x.strip()) for x in raw_recipients.split(",") if x.strip().isdigit()
                ]
        else:
            recipients = []

        success, flashes = process_add_comment(
            project=project,
            user=current_user,
            message=form.message.data,
            recipients=recipients,
        )

        # Flash all messages returned by the helper
        for msg, category in flashes:
            flash(msg, category)

        if success:
            db.session.commit()
            return redirect(url_for("projects.view_project", id=project_id))

    return redirect(url_for("projects.list_projects"))


# historique du projet
@projects_bp.route("/history/<int:id>", methods=["GET"])
@login_required
def history(id):
    project = Project.query.options(
        joinedload(Project.history).joinedload(ProjectHistory.updater).joinedload(User.p)
    ).get(id)

    if not project:
        return (
            jsonify({"Erreur": f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé."}),
            404,
        )

    if not (
        current_user.id == project.uid
        or any(member.pid == current_user.pid for member in project.members)
        or current_user.p.role
        in [
            "gestion",
            "direction",
            "admin",
        ]
    ):
        return (
            jsonify({"Erreur": "Vous ne pouvez pas accéder à l'historique de ce projet."}),
            404,
        )

    # create a list of quadriplets (status, updated_at, updated_by, budget_id)
    project_history = [
        {
            "status": entry.status,
            "date": entry.updated_at,
            "name": get_name(entry.updater.p, option="s", current_user=current_user),
            "bid_status": "Code budget affecté" if entry.budget_id else None,
        }
        for entry in project.history
    ]

    if current_user.p.role in ["gestion", "direction"]:
        # remove all draft modification events prior to first validation request
        while len(project_history) > 1 and project_history[-2]["status"] == "draft":
            del project_history[-2]

    # create html table
    history_html = render_template(
        "_history_modal.html",
        project_history=project_history,
        has_budget=project.has_budget,
    )
    return jsonify({"html": history_html})


# Information sur le budget du projet
@projects_bp.route("/budget/<int:id>", methods=["GET"])
@login_required
def project_budget(id):
    project = get_project_or_redirect(id, eagerload="m")

    if not project:
        return (
            jsonify({"Erreur": f"Le projet demandé (id = {id}) n'existe pas ou a été supprimé."}),
            404,
        )

    if not (
        current_user.id == project.uid
        or any(member.pid == current_user.pid for member in project.members)
        or current_user.p.role
        in [
            "gestion",
            "direction",
            "admin",
        ]
    ):
        return (
            jsonify({"Erreur": "Vous ne pouvez pas accéder au budget de ce projet."}),
            404,
        )

    # create html block
    budget_html = render_template("_budget_modal.html", project=project)
    return jsonify({"html": budget_html})


@projects_bp.route("/project/print/<int:id>", methods=["GET"])
@login_required
def print_fieldtrip_pdf(id):
    # get project
    project = get_project_or_redirect(id, eagerload="m")

    if not project or project.status != "validated" or project.location != "outer":
        flash("La page demandée n'existe pas ou a été supprimée.", "danger")
        return redirect(url_for("projects.list_projects"))

    if not (
        current_user.id == project.uid
        or any(member.pid == current_user.pid for member in project.members)
        or current_user.p.role
        in [
            "gestion",
            "direction",
            "admin",
        ]
    ):
        flash("Vous n'avez pas les autorisations nécessaires pour accéder à cette page.", "danger")
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
    school_year = auto_school_year()

    # get school year choices
    form3 = SelectYearsForm()
    form3.years.choices = get_years_choices()
    schoolyears_to_choose_from = len(form3.years.choices) > 1

    # default to current school year if not in session
    if "sy" not in session:
        session["sy"] = school_year.sy

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
