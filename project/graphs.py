import pandas as pd
import re

import plotly.express as px


def rgb_tint(str_rgb, tint):
    """Calculate color tint from string rgb color and tint level"""
    rgb = [int(c) for c in re.findall(r"\d{1,3}", str_rgb)]
    rgbt = [round(rgb[i] + (0.25 * tint * (255 - rgb[i]))) for i in range(3)]
    return f"rgb({rgbt[0]}, {rgbt[1]}, {rgbt[2]})"


def sunburst_chart(dfa):
    """Draw plotly sunburst chart"""
    color_palette = px.colors.qualitative.Pastel

    fig = px.sunburst(
        dfa,
        # path=["axis", "priority", "project"],  # with number of projects as leaf
        path=["axis", "priority"],
        values="project",
        custom_data=["axis", "priority"],
        color_discrete_sequence=color_palette,
    )

    fig.update_layout(
        height=840,
        width=840,
        margin=dict(t=80, l=10, r=10, b=20),
        font=dict(size=14),
        title="<b>Projets pédagogiques</b><br><sup>et projet d'établissement</sup>",
        # uniformtext=dict(minsize=10, mode="hide"),
        title_font_size=20,
    )

    # break long labels (axes and priorities) in smaller strings
    fig.data[0]["labels"] = [
        "<br>".join(re.findall(r"(.{15,}?|.{1,15})(?: |$)", x))
        for x in fig.data[0]["labels"]
    ]

    # add the number of projects to priority labels
    fig.data[0]["labels"] = [
        x
        + "<br>"
        + str(
            dfa.set_index("priority")["project"].to_dict().get(x.replace("<br>", " "), "")
        )
        for x in fig.data[0]["labels"]
    ]

    fig.update_traces(
        hovertemplate="Axe : <b>%{customdata[0]}</b><br>"
        + "Priorité : <b>%{customdata[1]}</b><br>"
        + "Projets : <b>%{value}</b>",
    )

    graph_html = fig.to_html(
        full_html=False, include_plotlyjs="directory", config={"displaylogo": False}
    ).replace("plotly.min.js", "static/js/plotly.min.js")

    return graph_html


def bar_chart(dfa, choices):
    """Draw stacked bar chart with tinted colors for each stacked bar"""
    color_palette = px.colors.qualitative.Pastel

    color_tints = [
        [rgb_tint(c, t) for t in range(len(choices["priorities"][i]))]
        for i, c in enumerate(color_palette[0 : len(choices["axes"])])
    ]

    custom_palette = []
    for i in range(len(choices["axes"])):
        custom_palette += [
            color_tints[i][j]
            for j in range(
                len(set(dfa["priority"]) & set([p[1] for p in choices["priorities"][i]]))
            )
        ]

    fig = px.bar(
        dfa,
        x="axis",
        y="project",
        color="priority",
        width=840,
        height=600 + 16 * len(pd.unique(dfa.priority)),
        title="<b>Projets pédagogiques</b><br><sup>et projet d'établissement</sup>",
        color_discrete_sequence=custom_palette,
        labels={
            "axis": "Axe",
            "priority": "Priorités",
            "project": "Projets",
        },
        hover_name="priority",
        hover_data={"axis": False, "priority": False},
    )

    fig.update_xaxes(
        tickangle=0,
        tickmode="array",
        tickvals=dfa["axis"],
        ticktext=[
            "<br>".join(re.findall(r"(.{15,}?|.{1,15})(?: |$)", x)) for x in dfa.axis
        ],
        title=None,
    )

    fig.update_yaxes(tickformat="d")  # ticks at integer values only

    fig.update_layout(
        legend={
            "x": 0,
            "y": -0.08 * (len(pd.unique(dfa.priority)) + 1),
        },
        title_font_size=20,
    )

    for i in range(len(fig.data)):
        fig.data[i].hovertext[0] = "<br>".join(
            re.findall(r"(.{55,}?|.{1,55})(?: |$)", fig.data[i].hovertext[0])
        )
    fig.update_traces(
        hovertemplate="Priorité : <b>%{hovertext}</b><br>Projets : <b>%{y}</b><extra></extra>",
        hoverlabel=dict(
            bordercolor="rgba(0,0,0,0)",  # Transparent border
            font=dict(color="rgb(68, 68, 68)"),
        ),
    )

    graph_html = fig.to_html(
        full_html=False, include_plotlyjs="directory", config={"displaylogo": False}
    ).replace("plotly.min.js", "static/js/plotly.min.js")

    return graph_html


def timeline_chart(dft):
    color_palette = px.colors.qualitative.Pastel

    fig = px.bar(
        dft,
        x=dft.columns[0],
        y=dft.columns[1:],
        width=940,
        height=600,
        title="<b>Chronologie</b><br><sup>des projet pédagogiques</sup>",
        labels={"variable": "Projet"},
        hover_data={dft.columns[0]: False, "value": False},
        color_discrete_sequence=color_palette,
    )

    fig.update_xaxes(tickangle=0)

    fig.update_yaxes(
        tickformat="d",  # integer values
        title="Projets",
    )

    fig.update_layout(title_font_size=20, showlegend=False)

    for i in range(len(fig.data)):
        fig.data[i].hovertemplate = fig.data[i].name

    graph_html = fig.to_html(
        full_html=False, include_plotlyjs="directory", config={"displaylogo": False}
    ).replace("plotly.min.js", "static/js/plotly.min.js")

    return graph_html
