from flask_login import current_user
from sqlalchemy import func

import pandas as pd

from datetime import datetime, date
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_datetime

import re

from . import db, logger

from .models import Personnel, Project, SchoolYear

from .projects import ProjectForm, choices, levels, sections


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
        personnel = Personnel.query.filter(Personnel.id == pid).first()
    elif uid:
        if isinstance(uid, str):
            uid = int(uid)
        personnel = Personnel.query.filter(Personnel.user.has(id=uid)).first()
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
    if not school_years:  # default divisions
        divisions = ",".join(get_divisions("default"))
    else:  # copy from the previous year
        sy_previous = f"{sy_start.year - 1} - {sy_end.year - 1}"
        previous_school_year = SchoolYear.query.filter(SchoolYear.sy == sy_previous).first()
        divisions = previous_school_year.divisions

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
                    if _sy.sy_start.year >= int(pe_start) and _sy.sy_end.year <= int(pe_end)
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
            return "Terminale" + (space + division[-1].upper()) * (len(division) > 1)
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
    elif division.startswith("msgs"):
        if "F" in arg:
            return "MS/GS" + (space + division[-1].upper()) * (len(division) > 4)
        else:
            return "ms/gs" + (space + division[-1].upper()) * (len(division) > 4)
    elif division.startswith("psms"):
        if "F" in arg:
            return "PS/MS" + (space + division[-1].upper()) * (len(division) > 4)
        else:
            return "ps/ms" + (space + division[-1].upper()) * (len(division) > 4)
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


def get_divisions(sy=None, section=None):
    """
    Generate a list of divisions or a dictionnary with a list of divisions by section, for the corresponding period sy.
    Args:
        sy (str):
            - "XXXX - YYYY": a single school year
            - "default": for empty database
            - "current": to get the current and next school years
            - "next": to get the next school year
            - "Projet Étab. XXXX - YYYY": projet d'établissement (for example)
            - None for all school years
        section (str):
            - "secondary", "elementary" or "kindergarten": to get divisions for a specific section
            - "sections": to get divisions by section, for all sections
            - None for all divisions
    Returns:
        list or dictionary:
            - An list of divisions for section, if section is in sections, ordered by level.
            - A dictionnary {section: list of divisions ordered by level} for all sections if section = "sections".
            - A list of all divisions if section is None, ordered by level.
    """

    # default divisions for a new database
    # tous les niveaux, avec deux classes (A et B) par niveaux
    if sy == "default":
        divisions = [level + name for level in levels["lfs"] for name in ["A", "B"]]
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

    # generate the list of school years from the argument sy
    school_years = get_school_years(sy)

    # filter for school_years
    if school_years:
        if len(school_years) == 1:
            divs = [
                db.session.query(SchoolYear.divisions)
                .filter(SchoolYear.sy == school_years[0])
                .first()
            ]  # returns a list of tuples
        else:
            divs = (
                db.session.query(SchoolYear.divisions).filter(SchoolYear.sy.in_(school_years)).all()
            )  # returns a list of tuples
    else:
        divs = db.session.query(SchoolYear.divisions).all()  # returns a list of tuples

    # Extract the results into a list of unique divisions
    division_list = list(set([division for div in divs for division in div[0].split(",")]))

    # filter for section
    if section:
        if section == "sections":
            divisions = {}
            for _section in sections:
                divisions[_section] = [
                    division
                    for division in division_list
                    if any(division.startswith(prefix) for prefix in levels[_section])
                ]
        else:
            divisions = [
                division
                for division in division_list
                if any(division.startswith(prefix) for prefix in levels[section])
            ]
    else:
        divisions = division_list

    # order the list
    if section:
        if section == "sections":
            for section in sections:
                divisions[section].sort(key=lambda s: division_sort_key(s, levels[section]))
        else:
            divisions.sort(key=lambda s: division_sort_key(s, levels[section]))
    else:
        divisions.sort(key=lambda s: division_sort_key(s, levels["lfs"]))

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


def get_projects_df(filter=None, sy=None, draft=True, data=None, labels=False):
    """Convert Project table to DataFrame
    filter: department name, project id
    sy: school year, "current", "next", time period (ex. Projet Étab.)
    draft: include draft projects
    data: db (save Pickle file), Excel (save .xlsx file), data (for data page),
          budget (for budget page)
    labels: True (replace codes with corresponding labels)

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
                projects = Project.query.filter(Project.school_year == school_years[0]).all()
        else:  # multiple school years
            if isinstance(filter, str):  # department
                projects = Project.query.filter(
                    Project.school_year.in_(school_years),
                    Project.departments.regexp_match(f"(^|,){filter}(,|$)"),
                ).all()
            else:
                projects = Project.query.filter(Project.school_year.in_(school_years)).all()
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
                lambda x: get_name(x, option="s" if data != "Excel" else None)
            )
            if data == "Excel":
                df.rename(columns={"pid": "user"}, inplace=True)

        df["members"] = df["members"].map(lambda x: ",".join([get_name(e) for e in x.split(",")]))

        df["location"] = df["location"].map(lambda c: get_label(c, "location"))

        df["divisions"] = df["divisions"].map(lambda divs: division_names(divs))

        df["requirement"] = df["requirement"].map(lambda c: get_label(c, "requirement"))

        if "uid" in df.columns.tolist():
            df["uid"] = df["uid"].apply(
                lambda x: get_name(uid=x, option="s" if data != "Excel" else None)
            )

        if "modified_by" in df.columns.tolist():
            df["modified_by"] = df["modified_by"].apply(
                lambda x: get_name(uid=x, option="s" if data != "Excel" else None)
            )

        if "validated_by" in df.columns.tolist():
            df["validated_by"] = df["validated_by"].apply(
                lambda x: get_name(uid=x, option="s" if data != "Excel" else None)
            )

    return df
