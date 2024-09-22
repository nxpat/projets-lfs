from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    IntegerField,
    BooleanField,
    DecimalField,
    RadioField,
    SelectField,
    SubmitField,
    widgets,
)

from wtforms.widgets import HiddenInput
from wtforms.fields import SelectMultipleField, DateField
from wtforms.validators import (
    InputRequired,
    Length,
    Optional,
    Regexp,
    ValidationError,
)
from markupsafe import Markup

import re

# valid website regex
web_address = (
    r"(https?://)?"
    r"(?![^ ]{256,})"
    r"(?:(?!-)[a-z0-9-]{1,63}(?<!-)\.){1,126}"
    r"(?![0-9]+( |\t|$))(?!-)[a-z0-9-]{2,63}(?<!-)"
)
prog = re.compile(web_address)

# choices for some ProjectForm() fields
choices = {}

choices["departments"] = [
    "Arts et Lettres",
    "Langues",
    "Mathématiques NSI",
    "Sciences",
    "Sciences humaines",
    "Sport",
    "Primaire",
    "Maternelle",
]

choices["secondaire"] = [
    "Terminale",
    "1eB",
    "1eA",
    "2eB",
    "2eA",
    "3eB",
    "3eA",
    "4eB",
    "4eA",
    "5eB",
    "5eA",
    "6eB",
    "6eA",
]

choices["primaire"] = [
    "cm2B",
    "cm2A",
    "cm1B",
    "cm1A",
    "ce2B",
    "ce2A",
    "ce1B",
    "ce1A",
    "cpB",
    "cpA",
]

choices["maternelle"] = [
    "gs",
    "ps/msB",
    "ps/msA",
]

choices["divisions"] = (
    choices["secondaire"] + choices["primaire"] + choices["maternelle"]
)

choices["axes"] = [
    ("Axe 1", "Lycée international"),
    ("Axe 2", "Bien être"),
    ("Axe 3", "École responsable (E3D) et entreprenante"),
    ("Axe 4", "Communauté innovante et apprenante"),
]

axes = {axe[0]: axe[1] for axe in choices["axes"]}

choices["priorities"] = [
    [
        (
            "A1 Priorité 1",
            "Valoriser les parcours multilingues et multiculturels dans le contexte d'un établissement français à l'étranger",
        ),
        ("A1 Priorité 2", "S'ouvrir au pays d'accueil et à l'international"),
    ],
    [
        ("A2 Priorité 1", "Accueillir, accompagner, aider"),
        (
            "A2 Priorité 2",
            "Optimiser les lieux et les temps scolaires pour un cadre de vie et de travail serein et apaisé",
        ),
        (
            "A2 Priorité 3",
            "Communiquer sereinement et efficacement pour une cohésion renforcée",
        ),
    ],
    [
        ("A3 Priorité 1", "Éduquer aux problématiques du monde d'aujourd'hui, E3D"),
        ("A3 Priorité 2", "Favoriser, encourager et valoriser les projets et échanges"),
        ("A3 Priorité 3", "Accompagner vers la réussite et l'excellence"),
    ],
    [
        (
            "A4 Priorité 1",
            "Accompagner et valoriser le développement professionnel du personnel",
        ),
        (
            "A4 Priorité 2",
            "Éduquer aux compétences du XXIe siècle : créativité, esprit critique, communication, coopération",
        ),
        (
            "A4 Priorité 3",
            "Développer des parcours éducatifs variés pour une offre éducative plus riche",
        ),
    ],
]

priorities = {p[0]: p[1] for priority in choices["priorities"] for p in priority}


class BulmaListWidget(widgets.ListWidget):

    def __call__(self, field, **kwargs):
        kwargs.setdefault("id", field.id)
        html = [f"<div {widgets.html_params(**kwargs)}>"]
        for subfield in field:
            if self.prefix_label:
                html.append(
                    f"<span class='field'>{subfield.label} {subfield(class_='checkbox')}</span>"
                )
            else:
                html.append(
                    f"<div class='tag is-primary is-medium pl-0 pr-4'><span class='field'>{subfield(class_='checkbox')} {subfield.label}</span></div>"
                )
        html.append("</div>")
        return Markup("".join(html))


class BulmaMultiCheckboxField(SelectMultipleField):
    widget = BulmaListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(html_tag="ul", prefix_label=False)
    option_widget = widgets.CheckboxInput()


class AtLeastOneRequired(object):
    def __call__(self, form, field):
        if len(field.data) == 0:
            raise ValidationError("Sélectionner au moins une option")


class ProjectForm(FlaskForm):

    class Meta:
        csrf = True
        locales = ("fr_FR", "fr")

    title = StringField(
        "Titre du projet",
        render_kw={"placeholder": "Titre du projet"},
        validators=[InputRequired(), Length(min=3, max=100)],
    )

    objectives = TextAreaField(
        "Objectifs pédagogiques",
        description="Objectifs pédagogiques du projet en accord avec les axes et les priorités du projet d'établissement (500 caractères max)",
        render_kw={
            "placeholder": "Objectifs pédagogiques du projet en accord avec les axes et les priorités du projet d'établissement"
        },
        validators=[InputRequired(), Length(max=500)],
    )

    description = TextAreaField(
        "Description du projet",
        description="Description du projet et calendrier prévisionnel des différentes actions et activités à mener (1000 caractères max)",
        render_kw={
            "placeholder": "Description du projet et calendrier prévisionnel des différentes actions et activités à mener"
        },
        validators=[InputRequired(), Length(max=1000)],
    )

    date_1 = DateField(
        "Date ou début du projet",
        description="Date du projet (projet ponctuel) ou début du projet",
        validators=[InputRequired()],
    )

    date_2 = DateField(
        "Fin du projet",
        description="Pour un projet se déroulant sur une période",
        validators=[Optional()],
    )

    teachers = SelectMultipleField(
        "Équipe enseignante",
        description="Utiliser Ctrl / Shift pour sélectionner plusieurs enseignants",
        validators=[InputRequired()],
    )

    axis = SelectField(
        "Axe du projet d'établissement",
        choices=choices["axes"],
        validators=[AtLeastOneRequired()],
    )

    priority = SelectField(
        "Priorité de l'axe",
        choices=[p for axe in choices["priorities"] for p in axe],
        validators=[AtLeastOneRequired()],
    )

    paths = BulmaMultiCheckboxField(
        "Parcours éducatifs",
        choices=["Avenir", "Artistique / Culturel", "Santé", "Citoyen"],
        validators=[AtLeastOneRequired()],
    )

    skills = BulmaMultiCheckboxField(
        "Compétences transversales",
        choices=[
            "Créativité",
            "Pensée critique",
            "Responsabilité",
            "Coopération",
            "Communication",
        ],
        validators=[AtLeastOneRequired()],
    )
    divisions = BulmaMultiCheckboxField(
        "Classes",
        choices=choices["divisions"],
        validators=[AtLeastOneRequired()],
    )

    indicators = TextAreaField(
        "Indicateurs d'évaluation",
        description="Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet (500 caractères max)",
        render_kw={
            "placeholder": "Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet"
        },
        validators=[InputRequired(), Length(max=500)],
    )

    mode = RadioField(
        "Travail des élèves",
        choices=["Individuel", "En groupe"],
        description="Le travail des élèves sur ce projet est individuel ou s'effectue en groupe",
        validators=[InputRequired(message="Choisir une option")],
    )

    requirement = RadioField(
        "Participation",
        choices=["Toute la classe", "Optionnel"],
        description="Toute la classe ou seulement les volontaires ou sélectionnés participent au projet",
        validators=[InputRequired(message="Choisir une option")],
    )

    location = RadioField(
        "Lieu",
        choices=["En classe", "En dehors de la classe"],
        description="Le projet se déroule en classe pendant les heures de cours habituelles ou en dehors des heures de cours",
        validators=[InputRequired(message="Choisir une option")],
    )

    students = IntegerField(
        "Nombre d'élèves",
        description="Nombre d'élève connu ou estimé participant au projet",
        validators=[InputRequired()],
    )

    website = StringField(
        "Site web",
        render_kw={"placeholder": "www.exemple.fr"},
        validators=[
            Regexp(prog, message="Cette adresse Web n'est pas valide"),
            Optional(),
            Length(min=5, max=1000),
        ],
    )

    fin_hse = IntegerField(
        "HSE",
        default=0,
        validators=[Optional()],
    )

    fin_exp = IntegerField(
        "Matériel",
        default=0,
        validators=[Optional()],
    )

    fin_trip = IntegerField(
        "Frais de déplacements",
        default=0,
        validators=[Optional()],
    )

    fin_int = IntegerField(
        "Frais d'intervention",
        default=0,
        validators=[Optional()],
    )

    submit = SubmitField("Enregistrer")


class SelectProjectForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])

    submit = SubmitField()


class CommentForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])

    message = TextAreaField(
        "Ajouter un commentaire",
        description="Maximum 500 caractères",
        validators=[InputRequired(), Length(max=500)],
    )

    submit = SubmitField("Envoyer")


class LockForm(FlaskForm):
    lock = RadioField(
        "Enregistrement et mise à jour des projets dans la base",
        choices=[("Ouvert"), "Fermé"],
        validators=[InputRequired()],
    )

    submit = SubmitField("Appliquer")


class ProjectFilterForm(FlaskForm):
    filter = SelectField(
        choices={
            "Établissement": ["LFS", "Projets à valider"],
            "Départements": choices["departments"],
        },
        default="LFS",
        validators=[InputRequired()],
    )

    submit = SubmitField("Filtrer")


class DownloadForm(FlaskForm):
    file = StringField(
        "Télécharger la base des projets au format Excel",
        widget=HiddenInput(),
        validators=[InputRequired()],
    )

    submit = SubmitField("Télécharger")
