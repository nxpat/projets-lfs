from flask_login import current_user
from sqlalchemy import func

import pandas as pd

from datetime import datetime, date
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_datetime

import re

from . import db, logger

from .models import Personnel, User, Project, SchoolYear

from .projects import ProjectForm, choices, axes, priorities


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_date_fr(date, withdate=True, withtime=False):
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


def get_name(pid=None, uid=None, option=None):
    if pid:
        personnel = db.session.get(Personnel, pid)
    elif uid:
        if isinstance(uid, str):
            uid = int(uid)
        personnel = db.session.get(Personnel, db.session.get(User, uid).pid)
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


def get_default_sy_dates(today=None):
    """Return default school year dates:
    Sept. 1st to Aug. 31st of the current school year.
    """
    if not today:
        today = get_datetime().date()

    sy_start_default = date(today.year - 1 if today.month < 9 else today.year, 9, 1)
    sy_end_default = date(today.year if today.month < 9 else today.year + 1, 8, 31)

    return sy_start_default, sy_end_default


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
            if today > _start and today < _end:
                if sy_start and sy_end:
                    if _start != sy_start or _end != sy_end:
                        if today > sy_start and today < sy_end:
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
    if not school_years:  # default divisions
        divisions = ",".join(get_divisions("default"))
    else:  # copy from the previous year
        sy_previous = f"{sy_start.year - 1} - {sy_end.year - 1}"
        previous_school_year = SchoolYear.query.filter(
            SchoolYear.sy == sy_previous
        ).first()
        divisions = previous_school_year.divisions

    current_school_year = SchoolYear(
        sy_start=sy_start, sy_end=sy_end, sy=sy, divisions=divisions
    )
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
                    sy_start=sy_start.replace(year=sy_start.year + 1),
                    sy_end=sy_end.replace(year=sy_end.year + 1),
                    sy=sy_next,
                    nb_projects=project_counts[_sy],
                    divisions=divisions,
                )
                db.session.add(next_school_year)
            else:
                logger.warning(
                    f"auto_school_year(): found {_sy} school year with {project_counts[_sy]} projects. Data not saved to db."
                )

    # update the database
    db.session.commit()

    return sy_start, sy_end, sy


def get_school_years(sy):
    """
    Generate a list of school years for the corresponding period sy.
    The return is used for querying the project database.

    Args:
        sy (str): A string indicating the desired school year(s). It can be:
            - "XXXX - YYYY": a single school year.
            - "current": to get the current and next school years.
            - "next": to get the next school year.
            - "Projet Étab. XXXX - YYYY": projet d'établissement (for example)
            - None: indicates all school years

    Returns:
        list: A list of school years. It may be empty or contain one or more
              school years.
    """
    # get the current school year details
    sy_start, sy_end, sy_current = auto_school_year()
    sy_next = f"{sy_start.year + 1} - {sy_end.year + 1}"

    school_years = []

    if sy:
        match = re.match(r"^(.+ )?(\d{4}) - (\d{4})$", sy)
        if match:
            if match.group(1) is None:  # only one school year
                school_years = [sy]
            else:  # projet d'établissement
                pe_start, pe_end = re.findall(r"\b\d{4}\b", sy)
                school_years = [
                    _sy.sy
                    for _sy in SchoolYear.query.all()
                    if _sy.sy_start.year >= int(pe_start)
                    and _sy.sy_end.year <= int(pe_end)
                ]
        elif sy == "current":
            school_years = [sy_current, sy_next]
        elif sy == "next":
            school_years = [sy_next]
        else:  # invalid input
            school_years = [sy_current]
    else:
        school_years = []  # all school years

    return school_years


def get_divisions(sy, section=None):
    """
    Generate a list of divisions for the corresponding period sy.

    Args:
        sy (str): A string indicating the desired school year(s). It can be:
            - "XXXX - YYYY": a single school year.
            - "current": to get the current and next school years.
            - "next": to get the next school year.
            - "Projet Étab. XXXX - YYYY": projet d'établissement (for example)
            - None: indicates all school years

    Returns:
        list or dictionary:
            - An ordered list of divisions for section if section in sections
            - A dictionnary {section:ordered list of divisions} for all sections if section = "sections"
            - An ordered list of all divisions for section is None.
    """

    # sections
    sections = ["secondaire", "primaire", "maternelle"]

    # levels
    levels = [
        "Te",
        "1e",
        "2e",
        "3e",
        "4e",
        "5e",
        "6e",
        "cm2",
        "cm1",
        "ce2",
        "ce1",
        "cp",
        "gs",
        "ps/ms",
    ]

    # default divisions for a new database
    if sy == "default":
        divisions = [level + name for level in levels for name in ["A", "B"]]
        return divisions

    # division order
    division_order = {}
    division_order["secondaire"] = [
        "Terminale",
        "Te",
        "1re",
        "1e",
        "2de",
        "2e",
        "3e",
        "4e",
        "5e",
        "6e",
    ]
    division_order["primaire"] = ["cm2", "cm1", "ce2", "ce1", "cp"]
    division_order["maternelle"] = ["gs", "ps/ms"]
    division_order["lfs"] = (
        division_order["secondaire"]
        + division_order["primaire"]
        + division_order["maternelle"]
    )

    def division_sort_key(s, custom_order):
        # Find the prefix
        for prefix in custom_order:
            if s.startswith(prefix):
                return (
                    custom_order.index(prefix),
                    s[len(prefix) :],
                )  # Return index and the rest of the string
        return (len(custom_order), s)  # If no prefix matches, sort at the end

    # generate the list of school years from the argument sy
    school_years = get_school_years(sy)

    if school_years:
        if len(school_years) == 1:
            divs = [
                db.session.query(SchoolYear.divisions)
                .filter(SchoolYear.sy == school_years[0])
                .first()
            ]  # returns a list of tuples
        else:
            divs = (
                db.session.query(SchoolYear.divisions)
                .filter(SchoolYear.sy.in_(school_years))
                .all()
            )  # returns a list of tuples
    else:
        divs = db.session.query(SchoolYear.divisions).all()  # returns a list of tuples

    # Extract the results into a list of unique divisions
    division_list = list(
        set([division for div in divs for division in div[0].split(",")])
    )

    # filter the list for section
    if section:
        if section == "sections":
            divisions = {}
            for _section in sections:
                divisions[_section] = [
                    division
                    for division in division_list
                    if any(
                        division.startswith(prefix) for prefix in division_order[_section]
                    )
                ]
        else:
            divisions = [
                division
                for division in division_list
                if any(division.startswith(prefix) for prefix in division_order[section])
            ]
    else:
        divisions = division_list

    # order the list
    if section:
        if section == "sections":
            for section in sections:
                divisions[section].sort(
                    key=lambda s: division_sort_key(s, division_order[section])
                )
        else:
            divisions.sort(key=lambda s: division_sort_key(s, division_order[section]))
    else:
        divisions.sort(key=lambda s: division_sort_key(s, division_order["lfs"]))

    return divisions


def row_to_dict(row):
    """Convert a SQLAlchemy row to a dictionary."""
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


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


def get_projects_df(filter=None, sy=None, draft=True, data=None, labels=False):
    """Convert Project table to DataFrame
    filter: department name, project id or None
    sy: school year, "current", "next", time period (ex. Projet Étab.) or None
    draft: include draft projects
    data: db (save Pickle file), Excel (save .xlsx file), data (for data page), budget (for budget page) or None
    labels: replace codes with meaningful values

    return: dataframe with projects data
    """

    # generate the list of school years from the argument sy
    school_years = get_school_years(sy)

    # Query data with filter and sy filters
    if isinstance(filter, int):  # single project
        projects = [Project.query.filter(Project.id == filter).first()]
    elif school_years:
        if len(school_years) == 1:  # single school year
            if isinstance(filter, str):  # department
                projects = Project.query.filter(
                    Project.school_year == school_years[0],
                    Project.departments.regexp_match(f"(^|,){filter}(,|$)"),
                ).all()
            else:
                projects = Project.query.filter(
                    Project.school_year == school_years[0]
                ).all()
        else:  # multiple school years
            if isinstance(filter, str):  # department
                projects = Project.query.filter(
                    Project.school_year.in_(school_years),
                    Project.departments.regexp_match(f"(^|,){filter}(,|$)"),
                ).all()
            else:
                projects = Project.query.filter(
                    Project.school_year.in_(school_years)
                ).all()
    else:  # all school years
        if isinstance(filter, str):  # department
            projects = Project.query.filter(
                Project.departments.regexp_match(f"(^|,){filter}(,|$)")
            ).all()
        else:
            projects = Project.query.all()

    # Convert to dictionary and process data
    projects_data = []
    for project in projects:
        project_dict = row_to_dict(project)

        if data != "budget":
            project_dict["members"] = ",".join(
                [str(member.pid) for member in project.members]
            )

        if data not in ["db", "Excel"]:
            project_dict["has_budget"] = project.has_budget()
            project_dict["nb_comments"] = len(project.comments)

        if data not in ["budget", "data", "db"]:
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

    if data not in ["budget", "data", "db"]:
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

    # Replace values by labels for members field and fields with choices defined as tuples
    if labels:
        if "pid" in df.columns.tolist():
            df["pid"] = df["pid"].apply(lambda x: get_name(x))
        df["members"] = df["members"].map(
            lambda x: ",".join([get_name(e) for e in x.split(",")])
        )
        df["axis"] = df["axis"].map(axes)
        df["priority"] = df["priority"].map(priorities)
        df["location"] = df["location"].map(lambda c: get_label(c, "location"))
        df["requirement"] = df["requirement"].map(lambda c: get_label(c, "requirement"))

    return df
