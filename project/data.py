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

from .models import Personnel
from .project import ProjectForm, choices

from .utils import (
    get_project_dates,
    get_school_years,
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
    n_secondary = len(df[~df.departments.str.split(",").map(set(choices["Secondaire"]).isdisjoint)])
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
        if member[2] in choices["Secondaire"]:
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
    divisions = get_divisions(sy, sections=["Lycée", "Collège", "Élémentaire", "Maternelle"])

    for section, divs in divisions.items():
        data[f"divisions-{section}"] = []
        # efficiently checks for overlaps between the split lists from the divisions column
        # and the division list from the section divs
        dff = df[~df.divisions.str.split(",").map(set(divs).isdisjoint)]
        n = len(dff)
        for division in divs:
            dff = df[df.divisions.str.split(",").apply(lambda x: division in x)]
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

    data["divisions-section"] = []
    df = df[~df.divisions.str.split(",").map(set(get_divisions(sy)).isdisjoint)]
    n = len(df)
    dff = df[~df.divisions.str.split(",").map(set(get_divisions(sy, "Secondaire")).isdisjoint)]
    n_s = len(dff)
    data["divisions-section"].append(
        {
            "category": "Secondaire",
            "count": n_s,
            "percentage": f"{n and n_s / n * 100 or 0:.0f}%",
            "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
        }
    )
    dff = df[~df.divisions.str.split(",").map(set(get_divisions(sy, "Primaire")).isdisjoint)]
    n_p = len(dff)
    data["divisions-section"].append(
        {
            "category": "Primaire",
            "count": n_p,
            "percentage": f"{n and n_p / n * 100 or 0:.0f}%",
            "projects": [{"id": index, "title": row["title"]} for index, row in dff.iterrows()],
        }
    )
    data["divisions-section"].append({"total": n})

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


def generate_pe_analysis(data):
    """Create PE analysis DataFrame :
    axes et priorités du projet d'établissement
    """
    dfa = pd.DataFrame(
        {
            "priority": [row["priority"] for row in data if row["count"] != 0],
            "axis": [row["axis"] for row in data if row["count"] != 0],
            "projects": [row["count"] for row in data if row["count"] != 0],
        }
    )
    return dfa


def generate_project_timeline(df, years_str):
    # 1. Get School Year data as a dictionary
    sy_dict = get_school_years(years_str)
    if not sy_dict:
        return pd.DataFrame()

    # 2. Pre-calculate the axis bounds
    all_years = sy_dict.values()
    sy_start_month = min(sy.sy_start.month for sy in all_years)
    sy_end_month = max(
        (sy.sy_end.month + 12 if sy.sy_end.year > sy.sy_start.year else sy.sy_end.month)
        for sy in all_years
    )

    # Generate French months
    sy_months = [
        format_date(datetime(2000, (m - 1) % 12 + 1, 1), format="MMMM", locale="fr_FR").capitalize()
        for m in range(sy_start_month, sy_end_month + 1)
    ]

    # X-Axis Title
    if years_str:
        prefix = "Année scolaire" if len(sy_dict) == 1 else "Projet d'établissement"
        x_axis_title = f"{prefix} {years_str}"
    else:
        x_axis_title = "Années scolaires"

    # 3. Build Data Dictionary (Optimized Loop)
    data_dict = {x_axis_title: sy_months}
    num_months = len(sy_months)

    for project in df.itertuples():
        # Get start year from '2024 - 2025' format
        sy_base_year = int(project.school_year[:4])

        # Determine relative month offsets
        p_start = project.start_date.month + (12 if project.start_date.year > sy_base_year else 0)
        p_end = project.end_date.month + (12 if project.end_date.year > sy_base_year else 0)

        # Calculate indices
        idx_start = max(0, p_start - sy_start_month)
        idx_end = min(num_months, p_end - sy_start_month + 1)

        project_calendar = [1 if idx_start <= i < idx_end else 0 for i in range(num_months)]

        # Header formatting
        title_wrapped = "<br>".join(re.findall(r"(.{75,}?|.{1,75})(?: |$)", project.title))
        dates = get_project_dates(project.start_date, project.end_date)
        divs = "<br>".join(
            re.findall(r"(.{75,}?|.{1,75})(?:,|$)", division_names(project.divisions, "s"))
        )

        data_dict[f"<b>{title_wrapped}</b><br>{dates}<br>{divs}"] = project_calendar

    # 4. Create DataFrame and Filter empty months
    dft = pd.DataFrame(data_dict)

    # Combined filter for July/August
    activity = dft.iloc[:, 1:].sum(axis=1)
    is_summer_empty = (dft[x_axis_title].isin(["Juillet", "Août"])) & (activity == 0)

    dft = dft[~is_summer_empty].reset_index(drop=True)

    return dft


def data_analysis(sy):
    # get projects DataFrame
    df = get_projects_df(draft=False, years=sy, data="data")

    # calculate projects distribution
    data = calculate_distribution(df, sy, choices)

    if graph_module:
        if len(df) > 0:
            # create DataFrame for the analysis of Projet d'établissement
            dfa = generate_pe_analysis(data["pe_chart"])

            # create project timeline DataFrame
            dft = generate_project_timeline(df, sy)

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
