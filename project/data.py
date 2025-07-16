import pandas as pd
import re

from datetime import datetime
from babel.dates import format_date

from .models import Personnel, SchoolYear
from .projects import ProjectForm

from .utils import get_project_dates


def get_personnel_choices():
    """Prepare personnel list"""
    return sorted(
        [
            (
                personnel.id,
                f"{personnel.name} {personnel.firstname}",
                personnel.department,
            )
            for personnel in Personnel.query.all()
        ],
        key=lambda x: x[1],
    )


def calculate_distribution(df, choices):
    """Calculate distribution for axes, priorities, departments, etc."""
    dist = {}
    N = len(df)
    dist["TOTAL"] = N

    for axis in choices["axes"]:
        n = len(df[df.axis == axis[0]])
        s = sum(df[df.axis == axis[0]]["nb_students"])
        dist[axis[0]] = (n, f"{N and n / N * 100 or 0:.0f}%")  # 0 if division by zero
        for priority in choices["priorities"][choices["axes"].index(axis)]:
            p = len(df[df.priority == priority[0]])
            dist[priority[0]] = (p, f"{n and p / n * 100 or 0:.0f}%", s)

    for department in choices["departments"]:
        d = len(df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")])
        s = sum(
            df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")]["nb_students"]
        )
        dist[department] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    d = len(df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)])
    if len(df) != 0:
        s = sum(
            df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)][
                "nb_students"
            ]
        )
    else:
        s = 0
    dist["secondary"] = (d, f"{N and d / N * 100 or 0:.0f}%", s)
    dist["primary"] = dist["Primaire"]
    dist["kindergarten"] = dist["Maternelle"]

    for member in choices["personnels"]:
        d = len(df[df.members.str.contains(f"(?:^|,){member[0]}(?:,|$)")])
        s = sum(df[df.members.str.contains(f"(?:^|,){member[0]}(?:,|$)")]["nb_students"])
        dist[member[0]] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    for path in ProjectForm().paths.choices:
        d = len(df[df.paths.str.contains(path)])
        s = sum(df[df.paths.str.contains(path)]["nb_students"])
        dist[path] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    for skill in ProjectForm().skills.choices:
        d = len(df[df.skills.str.contains(skill)])
        s = sum(df[df.skills.str.contains(skill)]["nb_students"])
        dist[skill] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    for section in ["secondaire", "primaire", "maternelle"]:
        dist[section] = len(
            df[~df.divisions.str.split(",").map(set(choices[section]).isdisjoint)]
        )
        n = dist[section]
        for division in choices[section]:
            d = len(df[df.divisions.str.contains(division)])
            dist[division] = (d, f"{n and d / n * 100 or 0:.0f}%")

    for m in ProjectForm().mode.choices:
        d = len(df[df["mode"] == m])
        s = sum(df[df["mode"] == m]["nb_students"])
        dist[m] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    for r in ProjectForm().requirement.choices:
        d = len(df[df.requirement == r[0]])
        s = sum(df[df.requirement == r[0]]["nb_students"])
        dist[r[0]] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    for loc in ProjectForm().location.choices:
        d = len(df[df.location == loc[0]])
        s = sum(df[df.location == loc[0]]["nb_students"])
        dist[loc[0]] = (d, f"{N and d / N * 100 or 0:.0f}%", s)

    return dist


def create_pe_analysis(dist, choices):
    """Create DataFrame for the analysis of:
    axes et priorités du projet d'établissement
    """
    dfa = pd.DataFrame(
        {
            "priority": [
                p[1] for axis in choices["priorities"] for p in axis if dist[p[0]][0] != 0
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
    return dfa


def create_project_timeline(df, timeframe):
    """Create project timeline DataFrame"""
    # get school year dates and calendar
    if not timeframe or not timeframe[0].isdigit():  # multiple school years
        if timeframe:  # projet d'établissement
            pe_start, pe_end = re.findall(r"\b\d{4}\b", timeframe)
            school_years = [
                sy
                for sy in SchoolYear.query.all()
                if sy.sy_start.year >= int(pe_start) and sy.sy_end.year <= int(pe_end)
            ]
        else:  # all school years
            school_years = SchoolYear.query.all()

        sy_start_month = None
        sy_end_month = None
        for _sy in school_years:
            if _sy:
                sy_start = _sy.sy_start
                sy_end = _sy.sy_end
            # last month of school year for use in range
            _sy_end_month = (
                sy_end.month + 12 if sy_end.year > sy_start.year else sy_end.month
            )
            if sy_start_month is None or sy_start.month < sy_start_month:
                sy_start_month = sy_start.month
            if sy_end_month is None or _sy_end_month > sy_end_month:
                sy_end_month = _sy_end_month

    else:  # single school year
        _sy = SchoolYear.query.filter(SchoolYear.sy == timeframe).first()
        sy_start = _sy.sy_start
        sy_end = _sy.sy_end

        sy_start_month = sy_start.month
        # last month of school year for use in range
        sy_end_month = sy_end.month + 12 if sy_end.year > sy_start.year else sy_end.month

    print(sy_start_month, sy_end_month)
    # school year calendar with French names
    sy_months = [
        format_date(
            datetime(2000, m % 12 if m != 12 else 12, 1), format="MMMM", locale="fr_FR"
        ).capitalize()
        for m in range(sy_start_month, sy_end_month + 1)
    ]
    print(sy_months)

    # x-axis title
    if timeframe:
        x_axis_title = (
            f"Année scolaire {timeframe}"
            if timeframe[0].isdigit()
            else f"Projet d'établissement {timeframe[-11:]}"
        )
    else:
        x_axis_title = "Années scolaires"

    dft = pd.DataFrame({x_axis_title: sy_months})

    for project in df.itertuples():
        project_calendar = [0] * len(sy_months)
        project_start_month = (
            project.start_date.month
            if project.start_date.year == int(project.school_year[:4])
            else project.start_date.month + 12
        )
        project_end_month = (
            project.end_date.month
            if project.end_date.year == int(project.school_year[:4])
            else project.end_date.month + 12
        )
        print(project_start_month, project_end_month)

        for m in range(project_start_month, project_end_month + 1):
            project_calendar[m - sy_start_month] = 1
        dft[
            f"<b>{project.title}</b>"
            + f"<br>{get_project_dates(project.start_date, project.end_date)}"
            + f"<br>{project.divisions.replace(',', ', ')}"
        ] = project_calendar

    # drop July and August rows if no projects
    dft = dft[~((dft.iloc[:, 0] == "Juillet") & (dft.iloc[:, 1:].sum(axis=1) == 0))]
    dft = dft[~((dft.iloc[:, 0] == "Août") & (dft.iloc[:, 1:].sum(axis=1) == 0))]

    return dft
