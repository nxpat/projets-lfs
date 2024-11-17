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

# choix des départements enseignants
choices["secondary"] = [
    "Arts et Lettres",
    "Langues",
    "Mathématiques NSI",
    "Sciences",
    "Sciences humaines",
    "Sport",
]

choices["primary"] = ["Primaire"]

choices["kindergarten"] = ["Maternelle"]

choices["departments"] = (
    choices["secondary"] + choices["primary"] + choices["kindergarten"]
)

choices["lfs"] = ["LFS"] + choices["departments"]

# choix des divisions (classes)
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

# choix des axes et priorités du projet d'étalissement
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

# choix des budgets
choices["budget"] = {
    "budget_hse": "HSE",
    "budget_exp": "Matériel",
    "budget_trip": "Frais de déplacement",
    "budget_int": "Frais d'intervention",
}

# choix du statut des projets
choices["statuts"] = [
    ("draft", "Brouillon"),
    ("ready-1", "Soumettre à validation initiale (inclusion au budget)"),
    ("adjust", "Ajuster"),
    ("ready", "Soumettre à validation finale"),
]


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
            raise Exception(f'no field named "{self.other_field_name}" in form')
        if self.other_field_name.startswith("budget_") and other_field.data != 0:
            InputRequired(self.message).__call__(form, field)
        elif self.other_field_name == "location" and other_field.data == "outer":
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

    start_date = DateField(
        "Date ou début du projet",
        validators=[InputRequired()],
    )

    start_time = TimeField(
        "Heure",
        validators=[Optional()],
    )

    end_date = DateField(
        "Fin du projet",
        validators=[Optional()],
    )

    end_time = TimeField(
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
        choices=[p for axis in choices["priorities"] for p in axis],
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
        description="Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet",
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
            ("in", "LFS, en classe"),
            ("out", "LFS, en dehors de la classe"),
            ("outer", "Sortie scolaire"),
        ],
        description="Le projet se déroule en classe pendant les heures de cours habituelles, en dehors des heures de cours ou en sortie scolaire",
        validators=[InputRequired(message="Choisir une option")],
    )

    fieldtrip = TextAreaField(
        "Sortie scolaire",
        render_kw={
            "placeholder": "À remplir pour une sortie scolaire : indiquer le lieu et l'adresse",
        },
        description="Préciser le lieu et l'adresse de la sortie scolaire",
        validators=[
            RequiredIf(
                "location", "Préciser le lieu et l'adresse de la sortie scolaire"
            ),
        ],
    )

    nb_students = IntegerField(
        "Nombre d'élèves",
        description="Nombre d'élèves connu ou estimé participant au projet",
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

    budget_hse = IntegerField(
        "HSE",
        default=0,
        validators=[Optional()],
    )

    budget_hse_c = TextAreaField(
        "Précisions sur le budget HSE",
        description="Préciser l'utilisation du budget HSE",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_hse", "Préciser l'utilisation du budget HSE"),
        ],
    )

    budget_exp = IntegerField(
        "Matériel",
        default=0,
        validators=[Optional()],
    )

    budget_exp_c = TextAreaField(
        "Précisions sur le budget matériel",
        description="Préciser l'utilisation du budget matériel",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_exp", "Préciser l'utilisation du budget matériel"),
        ],
    )

    budget_trip = IntegerField(
        "Frais de déplacements",
        default=0,
        validators=[Optional()],
    )

    budget_trip_c = TextAreaField(
        "Précisions sur le budget frais de déplacements",
        description="Préciser l'utilisation du budget pour les frais de déplacements",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_trip",
                "Préciser l'utilisation du budget frais de déplacements",
            ),
        ],
    )

    budget_int = IntegerField(
        "Frais d'intervention",
        default=0,
        validators=[Optional()],
    )

    budget_int_c = TextAreaField(
        "Précisions sur le budget frais d'intervention",
        description="Préciser l'utilisation du budget pour les frais d'intervention",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_int",
                "Préciser l'utilisation du budget frais d'intervention",
            ),
        ],
    )

    status = RadioField(
        "Statut du projet",
        choices=choices["statuts"],
        default="draft",
        description="Le projet sera conservé comme brouillon ou soumis à validation",
        validators=[InputRequired()],
    )

    submit = SubmitField("Enregistrer")

    def validate_end_date(form, field):
        if field.data < form.start_date.data:
            raise ValidationError("Choisir une date postérieure au début du projet")


class SelectProjectForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])

    submit = SubmitField()


class CommentForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])
    message = TextAreaField(
        "Ajouter un commentaire",
        description="Le message est posté ici sur cette fiche projet et envoyé par e-mail à l'équipe enseignante porteuse du projet ou aux gestionnaires",
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
