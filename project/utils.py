import logging

from flask import g, has_app_context
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload

from itertools import groupby
from operator import attrgetter
import pandas as pd
import numpy as np

from collections import Counter

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_datetime

import io
import csv
import re

from .models import (
    db,
    Personnel,
    User,
    Project,
    ProjectMember,
    ProjectHistory,
    Dashboard,
    SchoolYear,
)

from .project import choices, levels

logger = logging.getLogger(__name__)


def get_cached_personnel():
    """
    Fetches all Personnel records and caches them in the application context (g).
    Eliminates redundant DB queries for a table that rarely changes.
    """
    if has_app_context():
        if "personnel_cache" not in g:
            g.personnel_cache = Personnel.query.options(joinedload(Personnel.user)).all()
        return g.personnel_cache
    else:
        # Fallback for CLI/background tasks
        return Personnel.query.options(joinedload(Personnel.user)).all()


def invalidate_school_years_cache():
    if has_app_context() and "school_years_cache" in g:
        del g.school_years_cache


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


def get_project_dates(start_date, end_date, br=True):
    if end_date.date() == start_date.date():
        if end_date.time() == start_date.time():
            return get_date_fr(start_date, withtime=True)
        else:
            return f"{get_date_fr(start_date, withtime=False)} {'<br>' * br}de {get_date_fr(start_date, withdate=False)} à {get_date_fr(end_date, withdate=False)}"
    else:
        return f"Du {get_date_fr(start_date, withtime=True)} {'<br>' * br}au {get_date_fr(end_date, withtime=True)}"


def get_name(personnel, option=None, current_user=None):
    """
    Returns a formatted name based for a Personnel.
    If current_user is provided and match the target, returns 'moi'.
    """

    if personnel:
        # Handle the "moi" logic if current user IDs are provided
        if option and "s" in option:
            option = option.replace("s", "")

            if current_user and current_user.p.id == personnel.id:
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
    """create default record if Dashboard is empty
    and return the dashboard record
    """
    dash = Dashboard.query.first()

    if not dash:
        dash = Dashboard(lock=0)
        db.session.add(dash)
        db.session.commit()

    return dash


def get_school_year_choices(sy, sy_next):
    return [("current", f"Actuelle ({sy})"), ("next", f"Prochaine ({sy_next})")]


def get_calendar_constraints(form, sy_start, sy_end):
    choices["sy_date_min"] = sy_start
    choices["sy_date_max"] = sy_end

    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    # OPTIMIZATION: Dictionary lookup instead of DB query
    next_school_year = get_school_years().get(sy_next)

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
    departments = choices["departments"]

    personnels = get_cached_personnel()

    filtered_personnel = [
        p for p in personnels if p.department in departments and p.role != "inactive"
    ]

    filtered_personnel.sort(
        key=lambda p: (
            departments.index(p.department) if p.department in departments else len(departments),
            p.name,
        )
    )

    result = {}
    for dept, group in groupby(filtered_personnel, key=attrgetter("department")):
        result[dept] = [(p.id, f"{p.name} {p.firstname}") for p in group]

    return result


def get_divisions_choices(sy):
    return [(div, division_name(div)) for div in get_divisions(sy)]


def get_division_sections(form):
    return {
        section: [
            subfield.data
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
    # Utilize the cached get_school_years() to prevent another DB query
    all_sys = get_school_years()
    school_years = sorted([(sy, sy) for sy in all_sys.keys()], reverse=True)

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


def get_school_years(years_str=None):
    """
    Parses a string like "XXXX - YYYY", a single school year or a range of school years
    (projet d'établissement), or None for all shool years.
    Returns a dict: { 'SY_string': SchoolYear_Object }
    """

    # 1. Fetch from cache or DB
    if has_app_context():
        if "school_years_cache" not in g:
            g.school_years_cache = {sy_obj.sy: sy_obj for sy_obj in SchoolYear.query.all()}
        all_sys = g.school_years_cache
    else:
        # Fallback for CLI/background tasks outside request context
        all_sys = {sy_obj.sy: sy_obj for sy_obj in SchoolYear.query.all()}

    # 2. Filter the pre-fetched dictionary in Python
    if years_str is None:
        return all_sys
    else:
        parts = years_str.split(" - ")
        start_val = int(parts[0].strip())
        end_val = int(parts[1].strip()) if len(parts) > 1 else start_val + 1

        # Reconstruct the list of possible SY strings to query specifically
        # Example: "2024 - 2026" -> ["2024 - 2025", "2025 - 2026"]
        sy_to_fetch = [f"{y} - {y + 1}" for y in range(start_val, end_val)]

        return {sy: obj for sy, obj in all_sys.items() if sy in sy_to_fetch}


def auto_school_year(sy_start=None, sy_end=None):
    today = get_datetime().date()

    # get default school year dates
    sy_start_default, sy_end_default = get_default_sy_dates(today)

    # check if arguments are valid dates for the current school year
    if sy_start and sy_start > today:
        sy_start = sy_start_default
    if sy_end and sy_end < today:
        sy_end = sy_end_default

    # OPTIMIZATION: Use cached dictionary instead of SchoolYear.query.all()
    school_years_dict = get_school_years()
    school_years = list(school_years_dict.values())

    ## update the current school year if it exists
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
                            db.session.commit()
                            invalidate_school_years_cache()
                return school_year

    # set to default dates if no arguments
    if not sy_start or sy_start > today:
        sy_start = sy_start_default
    if not sy_end or sy_end < today:
        sy_end = sy_end_default

    sy = f"{sy_start.year} - {sy_end.year}"

    # OPTIMIZATION: Dictionary lookup instead of SchoolYear.query.filter().first()
    sy_previous = f"{sy_start.year - 1} - {sy_end.year - 1}"
    previous_school_year = school_years_dict.get(sy_previous)

    if previous_school_year:
        divisions = previous_school_year.divisions
    else:
        divisions = get_divisions("default")

    current_school_year = SchoolYear(sy_start=sy_start, sy_end=sy_end, sy=sy, divisions=divisions)
    db.session.add(current_school_year)

    # Initialize the next school year eventually if projects exist
    if not school_years and db.session.query(Project.id).count():
        results = (
            db.session.query(Project.school_year, func.count(Project.id))
            .group_by(Project.school_year)
            .all()
        )
        project_counts = {_sy: count for _sy, count in results}

        sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"
        for _sy in project_counts:
            if _sy == sy_next:
                next_school_year = SchoolYear(
                    sy_start=add_year(sy_start),
                    sy_end=add_year(sy_end),
                    sy=sy_next,
                    divisions=divisions,
                )
                db.session.add(next_school_year)
            else:
                logger.warning(
                    f"auto_school_year(): found {_sy} school year with {project_counts[_sy]} projects. School year not saved to db."
                )

    db.session.commit()
    invalidate_school_years_cache()

    return current_school_year


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


def division_names(divisions: list, arg: str = "") -> str:
    """Convert a comma-separated string of canonical divisions into their display names.

    Args:
        divisions (list): A list of canonical division names.
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
    arg = arg.replace("s", "")
    return separator.join([division_name(div, arg) for div in divisions])


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
        {division.strip() for divisions in divisions_list for division in divisions}
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


def get_label(field, choice):
    """get the label for the field choice"""
    return choices.get(field, {}).get(choice, None)


def query_projects(user=None, filter=None, years=None, data=None, order="desc"):
    """Query Project table
    filter (str): department name, "Mes projets", "Mes projets à valider", "LFS" or None, "Projets à valider", "Sans code budgétaire"
    years (str): school year or range of school years string (ex. Projet Étab.),
        fiscal year, None for all school years
    data (str): "data" (for data page), "budget" (for budget page), "budget_strict" for only approved projects with budget, None.
    order (str): query order by project.id "asc" or "desc".

    return: SQLAlchemy query object
    """

    # Base query
    query = Project.query

    # Apply the "Years" filter
    if years:
        if re.fullmatch(r"\d{4}", years):  # fiscal year
            query = query.filter(Project.school_year.contains(years))
        else:  # school year(s)
            school_years = get_school_years(years)
            if len(school_years) == 1:
                query = query.filter(Project.school_year == years)
            elif len(school_years) > 1:
                query = query.filter(Project.school_year.in_(school_years))

    # Define user_is_involved
    if user:
        user_is_involved = or_(
            Project.uid == user.id, Project.members.any(ProjectMember.pid == user.p.id)
        )

    # Apply the "Type / Role / Department" filter
    if user and filter == "Mes projets":
        query = query.filter(user_is_involved)

    elif user and filter == "Mes projets à valider":
        query = query.filter(user_is_involved)
        query = query.filter(Project.status.in_(["ready-1", "ready"]))

    elif user and filter == "Projets à valider":
        if user.p.role in ["gestion", "direction", "admin"]:
            query = query.filter(Project.status.in_(["ready-1", "ready"]))
        else:
            # Security fallback
            query = query.filter(Project.id == 0)

    elif filter == "Sans code budgétaire":
        query = query.filter(Project.budget_id.is_(None))

    elif filter != "LFS" and filter is not None:  # Department
        if data == "budget":
            query = query.join(Project.user).join(User.p).filter(Personnel.department == filter)
        else:
            query = query.filter(Project.members.any(ProjectMember.department == filter))

    # Exclude "draft" projects where applicable
    if user:
        if (
            filter not in [user.p.department, "Mes projets", "Mes projets à valider"]
            and user.p.role != "admin"
        ):
            query = query.filter(or_(Project.status != "draft", user_is_involved))
    else:
        query = query.filter(Project.status != "draft")

    # Apply "budget" filter: approved projects requesting funds or not
    if data == "budget":
        query = query.filter(
            or_(
                Project.status.in_(["validated-1", "validated", "validated-10"]),
                and_(
                    Project.status == "ready",
                    Project.history.any(ProjectHistory.status == "validated-1"),
                ),
            )
        )
    # Apply "budget_strict" filter: approved projects requesting funds
    elif data == "budget_strict":
        query = query.filter(
            Project.has_budget,
            or_(
                Project.status.in_(["validated-1", "validated", "validated-10"]),
                and_(
                    Project.status == "ready",
                    Project.history.any(ProjectHistory.status == "validated-1"),
                ),
            ),
        )
    # Apply "data" filter: for dat page
    elif data == "data":
        query = query.filter(Project.status.not_in(["draft", "ready-1", "rejected"]))

    # default : order by newest first (desc)
    if order == "asc":
        return query.order_by(Project.id)
    else:
        return query.order_by(Project.id.desc())


def get_projects_df(user=None, filter=None, years=None, data=None, order="desc"):
    """Convert Project table to DataFrame
    filter: department name
    years: school year or range of school years string (ex. Projet Étab.),
        fiscal year, None for all school years
    draft: include draft projects
    data: Excel (save .xlsx file), data (for data page),
          budget (for budget page), None
    labels: True (replace codes with corresponding labels)

    return: dataframe with projects data
    """

    # Query data with filter and years filters
    query = query_projects(user=user, filter=filter, years=years, data=data, order=order)

    # Eager loading
    if data == "Excel":
        query = query.options(
            joinedload(Project.user).joinedload(User.p),
            joinedload(Project.modifier).joinedload(User.p),
            joinedload(Project.validator).joinedload(User.p),
            joinedload(Project.members).joinedload(ProjectMember.p),
        )
    elif data == "data":
        query = query.options(
            joinedload(Project.user).joinedload(User.p),
            joinedload(Project.members).joinedload(ProjectMember.p),
        )
    else:
        query = query.options(
            joinedload(Project.user).joinedload(User.p),
        )

    projects = query.all()

    if not projects:
        return pd.DataFrame()

    # Build the base DataFrame
    records = [{c.name: getattr(p, c.name) for c in p.__table__.columns} for p in projects]
    df = pd.DataFrame.from_records(records)

    # set index
    if data == "Excel":
        df.set_index("id", inplace=True)

    # Column-wise ORM extraction
    df["department"] = [p.user.p.department if p.user and p.user.p else None for p in projects]
    df["has_budget"] = ["Oui" if p.has_budget else "Non" for p in projects]

    # Vectorized boolean mapping
    df["is_recurring"] = np.where(df["is_recurring"], "Oui", "Non")

    # Vectorized transformations
    if data == "data":
        df["members"] = [[get_name(m.p) for m in p.members] for p in projects]
        df["departments"] = [[m.department for m in p.members] for p in projects]

    elif data == "Excel":
        df["user"] = [get_name(p.user.p) if p.user and p.user.p else "" for p in projects]
        df.drop(columns=["uid"], inplace=True, errors="ignore")

        df["members"] = ["\n".join([get_name(m.p) for m in p.members]) for p in projects]
        df["departments"] = ["\n".join([m.department for m in p.members]) for p in projects]
        df["modified_by"] = [get_name(p.modifier.p) if p.modified_by else "" for p in projects]
        df["validated_by"] = [get_name(p.validator.p) if p.validated_by else "" for p in projects]

        # Vectorized list joining
        for col in ["skills", "paths"]:
            df[col] = df[col].apply(lambda x: "\n".join(x) if isinstance(x, list) else x)

        df["divisions"] = df["divisions"].apply(
            lambda divs: (
                "\n".join([division_name(d, "FS") for d in divs])
                if isinstance(divs, list)
                else divs
            )
        )

        # Vectorized dictionary lookups (much faster than .get() in a loop)
        df["requirement"] = df["requirement"].map(choices["requirement"]).fillna(df["requirement"])
        df["location"] = df["location"].map(choices["location"]).fillna(df["location"])

        # Apply custom CSV function to the whole column
        df["students"] = df["students"].apply(lambda x: students_to_csv(x) if x else "")

    # Vectorized math
    if data in ["data", "budget"]:
        for i in [1, 2]:
            df[f"budget_total_{i}"] = (
                df[f"budget_exp_{i}"].fillna(0)
                + df[f"budget_trip_{i}"].fillna(0)
                + df[f"budget_int_{i}"].fillna(0)
            )

        for budget in choices["budget"]:
            # Adds the two columns together using Pandas C-backend instantly
            df[budget] = df[f"{budget}_1"].fillna(0) + df[f"{budget}_2"].fillna(0)

    # Column filtering and ordering
    if data == "Excel":
        columns = list(df.columns)
        for col, pos in [("user", 1), ("department", 2), ("status", 5), ("has_budget", 6)]:
            if col in columns:
                columns.remove(col)
                columns.insert(pos, col)

    elif data == "budget":
        columns = [
            "id",
            "title",
            "school_year",
            "start_date",
            "end_date",
            "department",
            "nb_students",
            "budget_id",
            "modified_at",
            "status",
            "validated_at",
            "is_recurring",
            "has_budget",
        ] + choices["budgets"]

    elif data == "data":
        columns = [
            "id",
            "title",
            "school_year",
            "start_date",
            "end_date",
            "department",
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
            "budget_id",
            "modified_at",
            "status",
            "validated_at",
            "is_recurring",
            "has_budget",
        ] + choices["budgets"]

    else:
        columns = list(df.columns)

    # Ensure we only select columns that actually exist to prevent KeyErrors
    available_columns = [c for c in columns if c in df.columns]

    return df[available_columns]


def get_new_messages(user):
    if not user.new_messages:
        return []

    valid_ids = []
    for pid in user.new_messages:
        try:
            valid_ids.append(int(pid))
        except (TypeError, ValueError):
            continue

    if not valid_ids:
        return []

    counts = Counter(valid_ids)
    projects = Project.query.filter(Project.id.in_(counts.keys())).all()

    return [{"project": project, "count": counts[project.id]} for project in projects]


def get_project_division_bit(project) -> int:
    """
    Returns 1 if the project touches Primary, 2 if Secondary, or 3 if both.
    """
    divs = str(project.divisions or "").split(",")

    # Example logic using your existing levels dict:
    has_primary = any(d.strip().startswith(levels["Primaire"]) for d in divs)
    has_secondary = any(d.strip().startswith(levels["Secondaire"]) for d in divs)

    bit = 0
    if has_primary:
        bit |= 1
    if has_secondary:
        bit |= 2
    return bit if bit > 0 else 3  # Default to 3 (Both) as a safety fallback


def get_comment_recipients(project, user):
    creator = project.user.p
    members = [member.p for member in project.members]

    commenters = [comment.user.p for comment in project.comments]

    personnels = get_cached_personnel()
    gestionnaires_query = [p for p in personnels if p.role == "gestion"]

    project_bit = get_project_division_bit(project)

    gestionnaires = [
        p
        for p in gestionnaires_query
        if p.user
        and isinstance(p.user.preferences, dict)
        and (p.user.preferences.get("notify_new_msg_team", 0) & project_bit) > 0
    ]

    # Personnel recipients, filtered out for any None values
    recipients = set([r for r in ([creator] + members + commenters + gestionnaires) if r])

    # Don't include the current user
    recipients.discard(user.p)

    # Filter inactive personnels
    recipients = [r for r in recipients if r.role != "inactive"]

    return recipients


def students_to_csv(students: list[dict], separator: str = ",") -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n", delimiter=separator)

    for s in students:
        writer.writerow(
            [
                (s.get("division") or "").strip(),
                " " + (s.get("name") or "").strip(),
                " " + (s.get("firstname") or "").strip(),
            ]
        )

    # .rstrip() removes the very last trailing newline
    return buffer.getvalue().rstrip()
