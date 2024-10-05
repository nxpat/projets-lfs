from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    IntegerField,
    RadioField,
    SelectField,
    BooleanField,
    SubmitField,
    widgets,
)

from wtforms.widgets import HiddenInput
from wtforms.fields import SelectMultipleField, DateField, TimeField
from wtforms.validators import (
    InputRequired,
    Length,
    Optional,
    Regexp,
    ValidationError,
)
from markupsafe import Markup

import re

from datetime import datetime

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

choices["dpt-secondaire"] = [
    "Arts et Lettres",
    "Langues",
    "Mathématiques NSI",
    "Sciences",
    "Sciences humaines",
    "Sport",
]

choices["dpt-primat"] = [
    "Primaire",
    "Maternelle",
]

choices["departments"] = choices["dpt-secondaire"] + choices["dpt-primat"]

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


class RequiredIf:
    """
    Validator which makes a field required if another field is set
    """

    field_flags = ("requiredif",)

    def __init__(self, other_field_name, message=None):
        self.other_field_name = other_field_name
        self.message = message

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception('no field named "%s" in form' % self.other_field_name)
        if other_field.data != 0:
            InputRequired(self.message).__call__(form, field)
        else:
            Optional(self.message).__call__(form, field)


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
        description="Objectifs pédagogiques du projet en accord avec les axes et les priorités du projet d'établissement",
        render_kw={
            "placeholder": "Objectifs pédagogiques du projet en accord avec les axes et les priorités du projet d'établissement"
        },
        validators=[InputRequired()],
    )

    description = TextAreaField(
        "Description du projet",
        description="Description du projet et calendrier prévisionnel des différentes actions et activités à mener",
        render_kw={
            "placeholder": "Description du projet et calendrier prévisionnel des différentes actions et activités à mener"
        },
        validators=[InputRequired()],
    )

    date_1 = DateField(
        "Date ou début du projet",
        validators=[InputRequired()],
    )

    time_1 = TimeField(
        "Heure",
        validators=[Optional()],
    )

    date_2 = DateField(
        "Fin du projet",
        validators=[Optional()],
    )

    time_2 = TimeField(
        "Heure",
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
        description="Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet (1000 caractères max)",
        render_kw={
            "placeholder": "Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet"
        },
        validators=[Optional(), Length(max=1000)],
    )

    mode = RadioField(
        "Travail des élèves",
        choices=["Individuel", "En groupe"],
        description="Le travail des élèves sur ce projet est individuel ou s'effectue en groupe",
        validators=[InputRequired(message="Choisir une option")],
    )

    requirement = RadioField(
        "Participation",
        choices=["Toute la classe", "Optionnelle"],
        description="Toute la classe ou seulement les volontaires ou sélectionnés participent au projet",
        validators=[InputRequired(message="Choisir une option")],
    )

    location = RadioField(
        "Lieu",
        choices=[
            ("in", "En classe"),
            ("out", "En dehors de la classe"),
            ("outer", "Sortie scolaire"),
        ],
        description="Le projet se déroule en classe pendant les heures de cours habituelles, en dehors des heures de cours ou en sortie scolaire",
        validators=[InputRequired(message="Choisir une option")],
    )

    students = IntegerField(
        "Nombre d'élèves",
        description="Nombre d'élève connu ou estimé participant au projet",
        validators=[InputRequired()],
        render_kw={
            "min": "1",
            "max": "600",
            "style": "width: 5em",
        },
    )

    website = StringField(
        "Site web",
        render_kw={"placeholder": "www.exemple.fr"},
        validators=[
            Optional(),
            Regexp(prog, message="Cette adresse Web n'est pas valide"),
            Length(min=5, max=500),
        ],
    )

    fin_hse = IntegerField(
        "HSE",
        default=0,
        validators=[Optional()],
    )

    fin_hse_c = TextAreaField(
        "Précisions sur le budget HSE",
        description="Préciser l'utilisation du budget HSE",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("fin_hse", "Préciser l'utilisation du budget HSE"),
        ],
    )

    fin_exp = IntegerField(
        "Matériel",
        default=0,
        validators=[Optional()],
    )

    fin_exp_c = TextAreaField(
        "Précisions sur le budget matériel",
        description="Préciser l'utilisation du budget matériel",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("fin_exp", "Préciser l'utilisation du budget matériel"),
        ],
    )

    fin_trip = IntegerField(
        "Frais de déplacements",
        default=0,
        validators=[Optional()],
    )

    fin_trip_c = TextAreaField(
        "Précisions sur le budget frais de déplacements",
        description="Préciser l'utilisation du budget pour les frais de déplacements",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "fin_trip",
                "Préciser l'utilisation du budget frais de déplacements",
            ),
        ],
    )

    fin_int = IntegerField(
        "Frais d'intervention",
        default=0,
        validators=[Optional()],
    )

    fin_int_c = TextAreaField(
        "Précisions sur le budget frais d'intervention",
        description="Préciser l'utilisation du budget pour les frais d'intervention",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "fin_int",
                "Préciser l'utilisation du budget frais d'intervention",
            ),
        ],
    )

    state = RadioField(
        "État du projet",
        choices=[("draft", "Brouillon"), ("ready", "Soumettre à validation")],
        default="draft",
        description="Le projet sera conservé comme brouillon ou soumis à validation",
        validators=[InputRequired()],
    )

    submit = SubmitField("Enregistrer")

    def validate_date_2(self, field):
        if field.data < self.date_1.data:
            raise ValidationError("Choisir une date postérieure au début du projet")


class SelectProjectForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])

    submit = SubmitField()


class CommentForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])
    message = TextAreaField(
        "Ajouter un commentaire",
        description="Le message est posté sur la fiche projet et envoyé par e-mail",
        validators=[InputRequired()],
    )

    submit = SubmitField("Envoyer")


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


class LockForm(FlaskForm):
    lock = RadioField(
        "Enregistrement et mise à jour des projets dans la base",
        choices=["Ouvert", "Fermé"],
        validators=[InputRequired()],
    )

    submit = SubmitField("Appliquer")


class DownloadForm(FlaskForm):
    file = StringField(
        "Télécharger la base des projets au format Excel",
        widget=HiddenInput(),
        validators=[InputRequired()],
    )

    submit = SubmitField("Télécharger")


class SchoolYearForm(FlaskForm):
    sy_start = DateField(
        "Début",
        validators=[InputRequired()],
    )

    sy_end = DateField(
        "Fin",
        validators=[InputRequired()],
    )

    sy_auto = BooleanField(
        "Paramétrage automatique",
        default=True,
        description="Année scolaire du 1er septembre au 31 août de l'année suivante",
        validators=[Optional()],
    )

    submit = SubmitField("Paramétrer")

    def validate_sy_end(self, field):
        if field.data <= self.sy_start.data:
            raise ValidationError("Date incorrecte")
