import logging

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from itertools import groupby
from operator import attrgetter
import pandas as pd

from collections import Counter

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_datetime

import re

from .models import (
    db,
    Personnel,
    User,
    Project,
    ProjectComment,
    Dashboard,
    SchoolYear,
)

from .project import ProjectForm, choices, levels

logger = logging.getLogger(__name__)


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_date_fr(date, withdate=True, withtime=False, full_date=False):
    if isinstance(date, str):
        try:
            # remove microseconds and time zone information, then convert to datetime
            date = datetime.strptime(date.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "None"
    if not date or str(date) == "NaT":
        return "None"
    elif not withdate:
        return format_datetime(date, format="H'h'mm", locale="fr_FR")
    elif withtime:
        if full_date:
            return (
                format_datetime(date, format="EEEE d MMMM yyyy H'h'mm", locale="fr_FR")
                .capitalize()
                .removesuffix(" 0h00")
            )
        else:
            return (
                format_datetime(date, format="EEE d MMM yyyy H'h'mm", locale="fr_FR")
                .capitalize()
                .removesuffix(" 0h00")
            )
    else:
        if full_date:
            return format_date(date, format="EEEE d MMMM yyyy", locale="fr_FR").capitalize()
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


def get_name(pid=None, uid=None, option=None, current_user_pid=None, current_user_uid=None):
    """
    Returns a formatted name based on Personnel ID (pid) or User ID (uid).
    If current_user_pid or current_user_uid are provided and match the target, returns 'moi'.
    """
    if pid:
        personnel = Personnel.query.filter(Personnel.id == pid).first()
    elif uid:
        if isinstance(uid, str):
            uid = int(uid)
        personnel = Personnel.query.filter(Personnel.user.has(id=uid)).first()
    else:
        return "None"

    if personnel:
        # Handle the "moi" logic if current user IDs are provided
        if option and "s" in option:
            option = option.replace("s", "")

            if (current_user_pid and personnel.id == current_user_pid) or (
                current_user_uid and uid == current_user_uid
            ):
                return "moi"

        # Standard formatting
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


def get_default_sy_dates(today=None):
    """Return default school year dates:
    Sept. 1st to Aug. 31st of the current school year.
    """
    if not today:
        today = get_datetime().date()

    sy_start_default = date(today.year - 1 if today.month < 9 else today.year, 9, 1)
    sy_end_default = date(today.year if today.month < 9 else today.year + 1, 8, 31)

    return sy_start_default, sy_end_default


def add_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:
        return d.replace(year=d.year + 1, day=28)


def auto_dashboard():
    """create default record if Dashboard is empty"""
    if not Dashboard.query.first():
        db.session.add(Dashboard(lock=0))
        db.session.commit()


def get_school_year_choices(sy, sy_next):
    return [("current", f"Actuelle ({sy})"), ("next", f"Prochaine ({sy_next})")]


def get_calendar_constraints(form, sy_start, sy_end):
    choices["sy_date_min"] = sy_start
    choices["sy_date_max"] = sy_end

    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"
    next_school_year = SchoolYear.query.filter(SchoolYear.sy == sy_next).first()
    if next_school_year:
        choices["sy_next_date_min"] = next_school_year.sy_start
        choices["sy_next_date_max"] = next_school_year.sy_end
    else:
        choices["sy_next_date_min"] = sy_end + timedelta(1)
        choices["sy_next_date_max"] = sy_end + (sy_end - sy_start)

    date_constraints = {
        "min": sy_start if form.school_year.data == "current" else choices["sy_next_date_min"],
        "max": sy_end if form.school_year.data == "current" else choices["sy_next_date_max"],
    }
    form.start_date.render_kw = date_constraints
    form.end_date.render_kw = date_constraints
    return form


def get_member_choices():
    all_personnel = (
        Personnel.query.filter(Personnel.department.in_(choices["departments"]))
        .order_by(Personnel.department, Personnel.name)
        .all()
    )
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
        form.status.choices = [choices["status"][i] for i in [0, 1, 4]]
    elif project_status == "validated-1":
        form.status.choices = [choices["status"][i] for i in [2, 4]]
        form.status.description = "Le projet sera ajusté ou soumis à validation"
    elif project_status == "validated-10":
        form.status.choices = choices["status"][3:5]
        form.status.description = "Le projet sera ajusté ou soumis à validation"
    elif project_status == "ready":
        form.status.choices = [choices["status"][5]]
        form.status.description = "Le projet, déjà soumis à validation, sera ajusté"
        form.status.data = "adjust"
    else:
        form.status.choices = [choices["status"][0]]
        form.status.description = "Le projet sera conservé comme brouillon"
    return form


def get_years_choices(fy=False):
    school_years = sorted([(sy.sy, sy.sy) for sy in SchoolYear.query.all()], reverse=True)
    fiscal_years = (
        sorted(list(set([y for sy in school_years for y in sy[0].split(" - ")])), reverse=True)
        if fy
        else []
    )

    if len(school_years) > 1:
        school_years.insert(0, ("Toutes les années", "Toutes les années"))
        school_years.insert(1, ("2024 - 2027", "Projet Étab. 2024 - 2027"))

    return (school_years, fiscal_years) if fy else school_years


def get_axis(priority):
    for axis, priorities in choices["pe"].items():
        if priority in priorities:
            return axis
    return None


def get_comments_df(project_id):
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
    if df.empty:
        return pd.DataFrame(columns=["id", "pid", "message", "posted_at"]).set_index("id")
    df["pid"] = df["pid"].astype(str)
    return df.set_index("id")


def get_comment_recipients(project, current_user_pid):
    creator = project.user.pid
    members = [member.pid for member in project.members]
    users = [comment.user.pid for comment in ProjectComment.query.filter_by(project=project).all()]

    gestionnaires_query = (
        db.session.query(Personnel)
        .options(joinedload(Personnel.user))
        .filter(Personnel.role == "gestion")
        .all()
    )
    gestionnaires = [
        p.id
        for p in gestionnaires_query
        if p.user and p.user.preferences and "email=default-c" in p.user.preferences.split(",")
    ]

    recipients = set([creator] + members + users + gestionnaires)
    recipients.discard(current_user_pid)
    return list(recipients)


def auto_school_year(sy_start=None, sy_end=None):
    today = get_datetime().date()

    # get default school year dates
    sy_start_default, sy_end_default = get_default_sy_dates(today)

    # check if arguments are valid dates for the current school year
    # use default dates otherwise
    if sy_start and sy_start > today:
        sy_start = sy_start_default
    if sy_end and sy_end < today:
        sy_end = sy_end_default

    # get school years
    school_years = SchoolYear.query.all()

    ## update the current school year
    ## if it exists
    if school_years:
        for school_year in school_years:
            _start = school_year.sy_start
            _end = school_year.sy_end
            _sy = school_year.sy
            if today >= _start and today <= _end:
                if sy_start and sy_end:
                    if _start != sy_start or _end != sy_end:
                        if today >= sy_start and today <= sy_end:
                            school_year.sy_start = sy_start
                            school_year.sy_end = sy_end
                            sy = f"{sy_start.year} - {sy_end.year}"
                            school_year.sy = sy
                            # update the database
                            db.session.commit()
                return school_year.sy_start, school_year.sy_end, school_year.sy

    ## create the current school year
    ## the current school year was not found, so we create it
    # set to default dates if no arguments
    if not sy_start or sy_start > today:
        sy_start = sy_start_default
    if not sy_end or sy_end < today:
        sy_end = sy_end_default

    sy = f"{sy_start.year} - {sy_end.year}"

    # initialize divisions
    sy_previous = f"{sy_start.year - 1} - {sy_end.year - 1}"
    previous_school_year = SchoolYear.query.filter(SchoolYear.sy == sy_previous).first()
    if previous_school_year:  # copy from the previous year
        divisions = previous_school_year.divisions
    else:  # default divisions
        divisions = ",".join(get_divisions("default"))

    current_school_year = SchoolYear(sy_start=sy_start, sy_end=sy_end, sy=sy, divisions=divisions)
    db.session.add(current_school_year)

    # New database: initialize the number of projects for the current year and
    # the next year eventually
    if not school_years and db.session.query(Project.id).count():
        results = (
            db.session.query(Project.school_year, func.count(Project.id))
            .group_by(Project.school_year)
            .all()
        )
        project_counts = {_sy: count for _sy, count in results}

        sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"
        for _sy in project_counts:
            if _sy == sy:  # current year
                current_school_year.nb_projects = project_counts[_sy]
            elif _sy == sy_next:  # next year
                next_school_year = SchoolYear(
                    sy_start=add_year(sy_start),
                    sy_end=add_year(sy_end),
                    sy=sy_next,
                    nb_projects=project_counts[_sy],
                    divisions=divisions,
                )
                db.session.add(next_school_year)
            else:
                logger.warning(
                    f"auto_school_year(): found {_sy} school year with {project_counts[_sy]} projects. School year not saved to db."
                )

    # update the database
    db.session.commit()

    return sy_start, sy_end, sy


def get_school_years(years_str=None):
    """
    Parses a string like "XXXX - YYYY", a single school year or a range of school years
    (projet d'établissement), or None for all shool years.
    Returns a dict: { 'SY_string': SchoolYear_Object }
    """

    if years_str is None:
        school_years = SchoolYear.query.all()
    else:
        parts = years_str.split(" - ")
        start_val = int(parts[0].strip())
        end_val = int(parts[1].strip()) if len(parts) > 1 else start_val + 1

        # Reconstruct the list of possible SY strings to query specifically
        # Example: "2024 - 2026" -> ["2024 - 2025", "2025 - 2026"]
        sy_to_fetch = [f"{y} - {y + 1}" for y in range(start_val, end_val)]

        # Single efficient query using .in_()
        school_years = SchoolYear.query.filter(SchoolYear.sy.in_(sy_to_fetch)).all()

    return {sy_obj.sy: sy_obj for sy_obj in school_years}


def division_name(canonical_division: str, arg: str = "") -> str:
    """Get the display name for a given canonical division.

    Args:
        canonical_division (str): A string representing the canonical division.
        arg (str, optional): A string of flags that modify the output format.
            - "F": display the full division name.
            - "S": add a space before the division name (letter).

    Returns:
        str: The display name corresponding to the canonical division.
            Returns an empty string if the input does not match any known division formats.
    """

    division = canonical_division
    space = " " if "S" in arg else ""

    if division.startswith("0"):
        if "F" in arg:
            return "Terminale" + (" " + division[-1].upper()) * (len(division) > 1)
        else:
            return (
                "Terminale"
                if len(division) == 1
                else "Te" + (space + division[-1].upper()) * (len(division) > 1)
            )
    elif division.startswith("1"):
        if "F" in arg:
            return "1re" + (space + division[-1].upper()) * (len(division) > 1)
        else:
            return (
                "1re"
                if len(division) == 1
                else "1e" + (space + division[-1].upper()) * (len(division) > 1)
            )
    elif division.startswith("2"):
        if "F" in arg:
            return "2de" + (space + division[-1].upper()) * (len(division) > 1)
        else:
            return (
                "2de"
                if len(division) == 1
                else "2e" + (space + division[-1].upper()) * (len(division) > 1)
            )
    elif division.startswith(("3", "4", "5", "6")):
        return division[0] + "e" + (space + division[-1].upper()) * (len(division) > 1)
    elif division.startswith(("cm", "ce")):
        if "F" in arg:
            return division[:3].upper() + (space + division[-1].upper()) * (len(division) > 3)
        else:
            return division[:3] + (space + division[-1].upper()) * (len(division) > 3)
    elif division.startswith("mgs"):
        if "F" in arg:
            return "MS/GS" + (space + division[-1].upper()) * (len(division) > 3)
        else:
            return "ms/gs" + (space + division[-1].upper()) * (len(division) > 3)
    elif division.startswith("pms"):
        if "F" in arg:
            return "PS/MS" + (space + division[-1].upper()) * (len(division) > 3)
        else:
            return "ps/ms" + (space + division[-1].upper()) * (len(division) > 3)
    elif division.startswith(("cp", "gs", "ms", "ps")):
        if "F" in arg:
            return division[:2].upper() + (space + division[-1].upper()) * (len(division) > 2)
        else:
            return division[:2] + (space + division[-1].upper()) * (len(division) > 2)
    else:
        return ""


def division_names(divisions: str, arg: str = "") -> str:
    """Convert a comma-separated string of canonical divisions into their display names.

    Args:
        divisions (str): A comma-separated string of canonical division names.
            Each division should be a valid canonical division (e.g., "0", "1a", "cm1").
        arg (str): A string of flags that modify the output format.
            - "F": display the full division name.
            - "S": add a space before the division name (letter).
            - "s": add a space after each comma.

    Returns:
        str: A comma-separated string of display names corresponding to the input canonical divisions.
            Each entry in the list will be the formatted display name based on the
            provided canonical division and format flags. If a division cannot be converted, it
            will return None for that entry.
    """
    separator = ", " if "s" in arg else ","
    return separator.join([division_name(div, arg) for div in divisions.split(",")])


def get_divisions(sy=None, sections=None):
    """
    Generate a list of divisions or a dictionnary with a list of divisions by section, for the corresponding period sy.
    Args:
        sy (str):
            - a single school year or a range of school years (Projet d'Établissement for example)
            - "default": for empty database
            - None for all school years
        sections (str or list):
            - str: name of a section
            - list: list of sections
            - None: to get all divisions
    Returns:
        list or dictionary:
            - A list of divisions ordered by level, if sections is None or str.
            - A dictionnary {section: list of divisions ordered by level}, if sections is list.
    """

    # default divisions for a new database
    # returns two divisions (A et B) by level, for all levels
    if sy == "default":
        divisions = [level + name for level in levels["LFS"] for name in ["A", "B"]]
        return divisions

    def division_sort_key(s, custom_order):
        # Find the prefix
        for prefix in custom_order:
            if s.startswith(prefix):
                return (
                    custom_order.index(prefix),
                    s[len(prefix) :],
                )  # Return index and the rest of the string
        return (len(custom_order), s)  # If no prefix matches, sort at the end

    # get the school year dictionary for sy
    sy_dict = get_school_years(sy)

    # extract divisions
    divisions_list = [obj.divisions for obj in sy_dict.values() if obj.divisions]

    # get unique divisions
    division_list = list(
        {division.strip() for divisions in divisions_list for division in divisions.split(",")}
    )

    # filter for section
    if isinstance(sections, list):
        divisions = {}
        for _section in sections:
            divisions[_section] = [
                division
                for division in division_list
                if any(division.startswith(prefix) for prefix in levels[_section])
            ]
    elif isinstance(sections, str):
        divisions = [
            division
            for division in division_list
            if any(division.startswith(prefix) for prefix in levels[sections])
        ]
    else:
        divisions = division_list

    # order the list
    if isinstance(sections, list):
        for _section in sections:
            divisions[_section].sort(key=lambda s: division_sort_key(s, levels[_section]))
    else:
        divisions.sort(key=lambda s: division_sort_key(s, levels["LFS"]))

    return divisions


def row_to_dict(row):
    """Convert a SQLAlchemy row to a dictionary."""
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def get_label(choice, field):
    """get the label for the field choice"""
    if field == "location":
        return next(iter([x[1] for x in ProjectForm().location.choices if x[0] == choice]))
    elif field == "requirement":
        return next(iter([x[1] for x in ProjectForm().requirement.choices if x[0] == choice]))
    else:
        return None


def get_projects_df(
    filter=None, years=None, draft=True, data=None, labels=False, current_user_uid=None
):
    """Convert Project table to DataFrame
    filter: department name, project id
    years: school year or range of school years string (ex. Projet Étab.),
        fiscal year, None or "all" for all school years
    draft: include draft projects
    data: db (save Pickle file), Excel (save .xlsx file), data (for data page),
          budget (for budget page)
    labels: True (replace codes with corresponding labels)

    return: dataframe with projects data
    """

    # Query data with filter and years filters
    if isinstance(filter, int):  # single project
        projects = [Project.query.filter(Project.id == filter).first()]
    elif years is None or years == "all":  # all school years
        if isinstance(filter, str):  # department
            projects = Project.query.filter(
                Project.departments.regexp_match(f"(^|,){filter}(,|$)")
            ).all()
        else:
            projects = Project.query.all()
    else:
        if re.fullmatch(r"\d{4}", years):  # fiscal year
            projects = Project.query.filter(Project.school_year.contains(years)).all()
        else:  # school year(s)
            school_years = get_school_years(years)
            if len(school_years) == 1:  # single school year
                if isinstance(filter, str):  # department
                    projects = Project.query.filter(
                        Project.school_year == years,
                        Project.departments.regexp_match(f"(^|,){filter}(,|$)"),
                    ).all()
                else:
                    projects = Project.query.filter(Project.school_year == years).all()
            else:  # multiple school years
                if isinstance(filter, str):  # department
                    projects = Project.query.filter(
                        Project.school_year.in_(school_years),
                        Project.departments.regexp_match(f"(^|,){filter}(,|$)"),
                    ).all()
                else:
                    projects = Project.query.filter(Project.school_year.in_(school_years)).all()

    # Convert to dictionary and process data
    projects_data = []
    for project in projects:
        project_dict = row_to_dict(project)

        if data != "budget":
            project_dict["members"] = ",".join([str(member.pid) for member in project.members])

        if data not in ["db", "Excel"]:
            project_dict["has_budget"] = project.has_budget()
            project_dict["nb_comments"] = len(project.comments)

        if data == "Excel":
            project_dict["pid"] = project.user.pid
            del project_dict["uid"]

        project_dict["is_recurring"] = "Oui" if project_dict["is_recurring"] else "Non"

        projects_data.append(project_dict)

    # Set columns for DataFrame
    columns = list(Project.__table__.columns.keys())

    if data != "budget":
        columns.insert(7, "members")

    if data not in ["db", "Excel"]:
        columns.append("has_budget")
        columns.append("nb_comments")

    if data == "Excel":
        columns.remove("uid")
        columns.insert(1, "pid")

    # Convert to DataFrame
    df = pd.DataFrame(projects_data, columns=columns)

    # Set Id column as index
    if data != "db":
        df.set_index("id", inplace=True)

    # Filter columns of interest
    if data == "budget":
        columns_of_interest = [
            "title",
            "school_year",
            "start_date",
            "end_date",
            "departments",
            "nb_students",
            "modified_at",
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
            "modified_at",
            "status",
            "validated_at",
            "is_recurring",
            "has_budget",
        ] + choices["budgets"]
        df = df[columns_of_interest]

    # Add budget columns for "année scolaire"
    if data in ["data", "budget"]:
        for budget in choices["budget"]:
            df[budget] = df[[budget + "_1", budget + "_2"]].sum(axis=1)

    # Filter draft projects
    if not draft:
        df = df[df["status"] != "draft"]

    # Filter rejected projects
    if data in ["data", "budget"]:
        df = df[df["status"] != "rejected"]

    # Replace values by labels for members field and fields with choices defined as tuples
    if labels:
        if "pid" in df.columns.tolist():
            df["pid"] = df["pid"].apply(
                lambda x: get_name(
                    x, option="s" if data != "Excel" else None, current_user_uid=current_user_uid
                )
            )
            if data == "Excel":
                df.rename(columns={"pid": "user"}, inplace=True)

        df["members"] = df["members"].map(lambda x: ",".join([get_name(e) for e in x.split(",")]))

        df["location"] = df["location"].map(lambda c: get_label(c, "location"))

        df["divisions"] = df["divisions"].map(lambda divs: division_names(divs))

        df["requirement"] = df["requirement"].map(lambda c: get_label(c, "requirement"))

        if "uid" in df.columns.tolist():
            df["uid"] = df["uid"].apply(
                lambda x: get_name(
                    uid=x,
                    option="s" if data != "Excel" else None,
                    current_user_uid=current_user_uid,
                )
            )

        if "modified_by" in df.columns.tolist():
            df["modified_by"] = df["modified_by"].apply(
                lambda x: get_name(
                    uid=x,
                    option="s" if data != "Excel" else None,
                    current_user_uid=current_user_uid,
                )
            )

        if "validated_by" in df.columns.tolist():
            df["validated_by"] = df["validated_by"].apply(
                lambda x: get_name(
                    uid=x,
                    option="s" if data != "Excel" else None,
                    current_user_uid=current_user_uid,
                )
            )

    return df


def get_new_messages(user):
    if user.new_messages and user.new_messages.strip():
        msg_list = [pid.strip() for pid in user.new_messages.split(",") if pid.strip()]
        return dict(Counter(msg_list))

    return {}
