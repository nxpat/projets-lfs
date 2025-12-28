from flask import render_template

import pandas as pd
import re

from datetime import datetime
from babel.dates import format_date

try:
    from .graphs import sunburst_chart, pe_bar_chart, timeline_chart

    graph_module = True
except ImportError:
    graph_module = False

from .models import Personnel, SchoolYear
from .projects import ProjectForm, choices

from .utils import (
    get_project_dates,
    division_name,
    division_names,
    get_divisions,
    get_projects_df,
)


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


def calculate_distribution(df, sy, choices):
    """Calculate distribution for axes, priorities, departments, etc."""
    N = len(df)
    data = {}

    # Projet d'établissement
    data["pe"] = []
    data["pe_chart"] = []  # charts for PE
    for axis, priorities in choices["pe"].items():
        dff = df[df.axis == axis]
        n = len(dff)
        data["pe"].append(
            {
                "axis": axis,
                "count": n,
                "percentage": f"{N and n / N * 100 or 0:.0f}%",  # handle division by zero
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
        for priority in priorities:
            dff = df[df.priority == priority]
            p = len(dff)
            data["pe"].append(
                {
                    "priority": priority,
                    "count": p,
                    "percentage": f"{n and p / n * 100 or 0:.0f}%",
                    "projects": [
                        {"id": index, "title": row["title"]} for index, row in dff.iterrows()
                    ],
                }
            )
            data["pe_chart"].append(
                {
                    "axis": axis,
                    "priority": priority,
                    "count": p,
                }
            )
    data["pe"].append({"total": N})

    # Departments
    data["departments"] = []
    for department in choices["departments"]:
        dff = df[df.departments.str.contains(f"(?:^|,){department}(?:,|$)")]
        d = len(dff)
        data["departments"].append(
            {
                "category": department,
                "count": d,
                "percentage": f"{N and d / N * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["departments"].append({"total": N})

    # teachers
    n_secondary = len(df[~df.departments.str.split(",").map(set(choices["secondary"]).isdisjoint)])
    n_elementary = len(df[df.departments.str.contains("(?:^|,)Élémentaire(?:,|$)")])
    n_kindergarten = len(df[df.departments.str.contains("(?:^|,)Maternelle(?:,|$)")])
    n_other = N - n_secondary - n_elementary - n_kindergarten

    data["teachers-secondary"] = []
    data["teachers-elementary"] = []
    data["teachers-kindergarten"] = []
    data["teachers-other"] = []

    for member in get_personnel_choices():
        dff = df[df.members.str.contains(f"(?:^|,){member[0]}(?:,|$)")]
        d = len(dff)
        if member[2] in choices["secondary"]:
            section = "teachers-secondary"
            n = n_secondary
        elif member[2] == "Élémentaire":
            section = "teachers-elementary"
            n = n_elementary
        elif member[2] == "Maternelle":
            section = "teachers-kindergarten"
            n = n_kindergarten
        else:
            section = "teachers-other"
            n = n_other

        data[section].append(
            {
                "category": member[1],
                "count": d,
                "percentage": f"{n and d / n * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["teachers-secondary"].append({"total": n_secondary})
    data["teachers-elementary"].append({"total": n_elementary})
    data["teachers-kindergarten"].append({"total": n_kindergarten})
    data["teachers-other"].append({"total": n_other})

    # Paths
    data["paths"] = []
    for path in ProjectForm().paths.choices:
        dff = df[df.paths.str.contains(path)]
        d = len(dff)
        data["paths"].append(
            {
                "category": path,
                "count": d,
                "percentage": f"{N and d / N * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["paths"].append({"total": N})

    # Skills
    data["skills"] = []
    for skill in ProjectForm().skills.choices:
        dff = df[df.skills.str.contains(skill)]
        d = len(dff)
        data["skills"].append(
            {
                "category": skill,
                "count": d,
                "percentage": f"{N and d / N * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["skills"].append({"total": N})

    # Divisions
    divisions = get_divisions(sy, "sections")

    for section, divisions in divisions.items():
        data[f"divisions-{section}"] = []
        dff = df[~df.divisions.str.split(",").map(set(divisions).isdisjoint)]
        n = len(dff)
        for division in divisions:
            dff = df[df.divisions.str.contains(division)]
            d = len(dff)
            data[f"divisions-{section}"].append(
                {
                    "category": division_name(division),
                    "count": d,
                    "percentage": f"{n and d / n * 100 or 0:.0f}%",
                    "projects": [
                        {"id": index, "title": row["title"]} for index, row in dff.iterrows()
                    ],
                }
            )
        data[f"divisions-{section}"].append({"total": n})

    # Mode
    data["mode"] = []
    for m in ProjectForm().mode.choices:
        dff = df[df["mode"] == m]
        d = len(dff)
        data["mode"].append(
            {
                "category": m,
                "count": d,
                "percentage": f"{N and d / N * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["mode"].append({"total": N})

    # Requirement
    data["requirement"] = []
    for r in ProjectForm().requirement.choices:
        dff = df[df.requirement == r[0]]
        d = len(dff)
        data["requirement"].append(
            {
                "category": r[1],
                "count": d,
                "percentage": f"{N and d / N * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["requirement"].append({"total": N})

    # Location
    data["location"] = []
    for loc in ProjectForm().location.choices:
        dff = df[df.location == loc[0]]
        d = len(dff)
        data["location"].append(
            {
                "category": loc[1],
                "count": d,
                "percentage": f"{N and d / N * 100 or 0:.0f}%",
                "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
            }
        )
    data["location"].append({"total": N})

    return data


def create_pe_analysis(data):
    """Create PE analysis DataFrame :
    axes et priorités du projet d'établissement
    """
    dfa = pd.DataFrame(
        {
            "priority": [row["priority"] for row in data if row["count"] != 0],
            "axis": [row["axis"] for row in data if row["count"] != 0],
            "project": [row["count"] for row in data if row["count"] != 0],
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
            _sy_end_month = sy_end.month + 12 if sy_end.year > sy_start.year else sy_end.month
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

    # school year calendar with French names
    sy_months = [
        format_date(
            datetime(2000, m % 12 if m != 12 else 12, 1), format="MMMM", locale="fr_FR"
        ).capitalize()
        for m in range(sy_start_month, sy_end_month + 1)
    ]

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

        for m in range(project_start_month, project_end_month + 1):
            project_calendar[m - sy_start_month] = 1
        dft[
            "<b>"
            + "<br>".join(re.findall(r"(.{75,}?|.{1,75})(?: |$)", project.title))
            + "</b>"
            + f"<br>{get_project_dates(project.start_date, project.end_date)}"
            + "<br>"
            + "<br>".join(
                re.findall(r"(.{75,}?|.{1,75})(?:,|$)", division_names(project.divisions, "s"))
            )
        ] = project_calendar

    # drop July and August rows if no projects
    dft = dft[~((dft.iloc[:, 0] == "Juillet") & (dft.iloc[:, 1:].sum(axis=1) == 0))]
    dft = dft[~((dft.iloc[:, 0] == "Août") & (dft.iloc[:, 1:].sum(axis=1) == 0))]

    return dft


def data_analysis(sy):
    # get projects DataFrame
    df = get_projects_df(draft=False, sy=sy, data="data")

    # calculate projects distribution
    data = calculate_distribution(df, sy, choices)

    if graph_module:
        if len(df) > 0:
            # create DataFrame for the analysis of Projet d'établissement
            dfa = create_pe_analysis(data["pe_chart"])

            # create project timeline DataFrame
            dft = create_project_timeline(df, sy)

            # sunburst chart
            # axes et priorités du projet d'établissement
            graph_html = sunburst_chart(dfa)

            # stacked bar chart
            # axes et priorités du projet d'établissement
            graph_html2 = pe_bar_chart(dfa, choices["pe"])

            # stacked bar chart
            # timeline
            graph_html3 = timeline_chart(dft)
        else:
            graph_html = None
            graph_html2 = None
            graph_html3 = None
    else:
        graph_html, graph_html2, graph_html3 = [
            "Ressources serveur insuffisantes." for i in range(3)
        ]

    return render_template(
        "_data.html",
        data=data,
        df=df,
        choices=choices,
        graph_html=graph_html,
        graph_html2=graph_html2,
        graph_html3=graph_html3,
    )
