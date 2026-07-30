import re
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    widgets,
)
from wtforms.fields import DateField, SelectMultipleField, TimeField
from wtforms.validators import (
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)
from wtforms.widgets import HiddenInput

# web address regex
re_web_address = (
    r"(https?://)?"
    r"(?![^ ]{256,})"
    r"(?:(?!-)[a-z0-9-]{1,63}(?<!-)\.){1,126}"
    r"(?![0-9]+( |\t|$))(?!-)[a-z0-9-]{2,63}(?<!-)"
)
prog_web_address = re.compile(re_web_address)

# fieldtrip external people list regex
# [^\W\d_] matches any unicode letter only
prog_ext_people = re.compile(
    r"^(((^| +)(([^\W\d_][-' ][^\W\d_]|[^\W\d_])+|\(stagiaire\))){2,5}(,|$))+$"
)

# choices for some ProjectForm() fields
choices = {}

# roles
choices["role"] = ["direction", "gestion", "admin"]

# choix des départements enseignants
choices["Secondaire"] = [
    "Arts et technologie",
    "Langues",
    "Lettres",
    "Mathématiques NSI",
    "Sciences",
    "Sciences humaines",
    "Sport",
    "Vie Scolaire",
]

choices["Primaire"] = [
    "Élémentaire",
    "Maternelle",
    "ASEM",
]

choices["Administration"] = ["Administration"]

choices["departments"] = choices["Secondaire"] + choices["Primaire"] + choices["Administration"]

choices["lfs"] = ["LFS"] + choices["departments"]

# choix des axes et priorités du projet d'étalissement
choices["pe"] = {
    "Lycée international": [
        "Valoriser les parcours multilingues et multiculturels dans le contexte d'un établissement français à l'étranger",
        "S'ouvrir au pays d'accueil et à l'international",
    ],
    "Bien être": [
        "Accueillir, accompagner, aider",
        "Optimiser les lieux et les temps scolaires pour un cadre de vie et de travail serein et apaisé",
        "Communiquer sereinement et efficacement pour une cohésion renforcée",
    ],
    "École responsable (E3D) et entreprenante": [
        "Éduquer aux problématiques du monde d'aujourd'hui, E3D",
        "Favoriser, encourager et valoriser les projets et échanges",
        "Accompagner vers la réussite et l'excellence",
    ],
    "Communauté innovante et apprenante": [
        "Accompagner et valoriser le développement professionnel du personnel",
        "Éduquer aux compétences du XXIe siècle : créativité, esprit critique, communication, coopération",
        "Développer des parcours éducatifs variés pour une offre éducative plus riche",
    ],
}

# choix des budgets
choices["budget"] = {
    "budget_hse": "HSE",
    "budget_exp": "Matériel",
    "budget_trip": "Transport",
    "budget_int": "Intervention",
    "budget_total": "Total",
}

choices["budgets"] = [*choices["budget"]] + [b + f"_{n}" for b in choices["budget"] for n in [1, 2]]

# choix des parcours éducatifs
choices["paths"] = ["Avenir", "Artistique / Culturel", "Santé", "Citoyen"]

# choix des compétences transversales
choices["skills"] = [
    "Créativité",
    "Pensée critique",
    "Responsabilité",
    "Coopération",
    "Communication",
]

# choix du mode de travail des élèves
choices["mode"] = ["Individuel", "En groupe", "Individuel et en groupe"]

# choix de la participation
choices["requirement"] = {"yes": "Toute la classe", "no": "Optionnelle", "free": "Libre"}

# choix du lieu
choices["location"] = {
    "in": "LFS, en classe",
    "out": "LFS, en dehors de la classe",
    "outer": "Sortie scolaire",
    "trip": "Voyage scolaire",
}

# choix du statut des projets
choices["status"] = [
    ("draft", "Brouillon"),
    ("ready-1", "Demande d'accord et inclusion au budget"),
    ("validated-1", "Ajuster"),
    ("validated-10", "Ajuster"),
    ("ready", "Demande de validation"),
    ("adjust", "Ajuster"),
]

# filter choices
choices["filter"] = {
    "Établissement": ["LFS", "Projets à valider"],
    "Mes projets": ["Mes projets", "Mes projets à valider"],
    "Départements": choices["departments"],
}
choices["filter-user"] = {
    key: [item for item in value if item != "Projets à valider"]
    for key, value in choices["filter"].items()
}
choices["filter-budget"] = {
    "Établissement": ["LFS"],
    "Départements": choices["departments"],
}
choices["filter-budget_id"] = {
    "Établissement": ["LFS", "Sans code budgétaire"],
    "Départements": choices["departments"],
}

# Choices mapping for bitwise: 1 = Primaire, 2 = Secondaire
choices["level"] = ((1, "Primaire"), (2, "Secondaire"))

# Ordered levels by section
# Canonical division names are obtained by adding the division letter ("A", "B", etc.) to the level
levels = {}
levels["Lycée"] = ("0", "1", "2")
levels["Collège"] = ("3", "4", "5", "6")
levels["Secondaire"] = levels["Lycée"] + levels["Collège"]
levels["Élémentaire"] = ("cm2", "cm1", "ce2", "ce1", "cp")
levels["Maternelle"] = ("gs", "mgs", "ms", "pms", "ps")
levels["Primaire"] = levels["Élémentaire"] + levels["Maternelle"]
levels["LFS"] = levels["Secondaire"] + levels["Primaire"]

# valid division names ("classes")
prog_divisions = [
    (
        re.compile(r"(0e?|t(e|a?le|erminale)?) *([a-d])?", re.IGNORECASE),
        "0",
        r"\3",
    ),  # Terminale
    (re.compile(r"(1(e|(e|è)?re)?|première) *([a-d])?", re.IGNORECASE), "1", r"\4"),  # Première
    (re.compile(r"(2(e|n?de)?|seconde) *([a-d])?", re.IGNORECASE), "2", r"\3"),  # Seconde
    (
        re.compile(r"([3-6])(e|(e|è)me)? *([a-d])?", re.IGNORECASE),
        r"\1",
        r"\4",
    ),  # collège
    (
        re.compile(r"((cm|ce)[12]|cp) *([a-d])?", re.IGNORECASE),
        r"\1",
        r"\3",
    ),  # élémentaire
    (
        re.compile(r"(gs|ms|ps) *([a-d])?", re.IGNORECASE),
        r"\1",
        r"\2",
    ),  # maternelle
    (re.compile(r"(ms/gs|msgs|mgs) *([a-d])?", re.IGNORECASE), "mgs", r"\2"),  # maternelle
    (re.compile(r"(ps/ms|psms|pms) *([a-d])?", re.IGNORECASE), "pms", r"\2"),  # maternelle
]


def valid_division(division, canonical_divisions):
    """Check if division is a valid canonical division
    Args:
        - division (str)
        - canonical_divisions (list) : list of canonical divisions
    Returns:
        The canonical division or None
    """

    for pattern, replacement_level, replacement_name in prog_divisions:
        # check if division is a valid division name
        match = pattern.fullmatch(division)
        if match:
            # convert to canonical division name
            canonical_division = match.expand(replacement_level).lower()  # level in lowercase
            canonical_name = match.expand(replacement_name)
            if canonical_name:
                canonical_division += canonical_name.upper()  # division name in uppercase

            # check if division is in the list of divisions
            if canonical_division in canonical_divisions:
                return canonical_division
            else:
                return None

    # if no division matched, return None
    return None


class RequiredIf:
    """WTForms validator that dynamically makes a field required based on another field's value or condition.

    Usage:
        # 1. Required if another field is truthy/has data:
        field = StringField(..., validators=[RequiredIf('budget_hse_1')])

        # 2. Required if another field matches specific value(s):
        field = StringField(..., validators=[RequiredIf('location', values=['outer', 'trip'])])

        # 3. Required based on custom logic (e.g., checking multiple fields):
        field = StringField(..., validators=[
            RequiredIf('requirement', condition=lambda other, form: other.data == 'no' and form.status.data in ['ready', 'adjust'])
        ])
    """

    def __init__(
        self,
        other_field_name: str,
        values: Sequence[Any] | Any | None = None,
        condition: Callable[[Any, Any], bool] | None = None,
        message: str | None = None,
    ):
        self.other_field_name = other_field_name
        self.message = message
        self.condition = condition

        # Normalize single value or sequence into a tuple
        if values is not None:
            self.values = tuple(values) if isinstance(values, (list, tuple, set)) else (values,)
        else:
            self.values = None

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)
        if not other_field:
            raise KeyError(f'No field named "{self.other_field_name}" in form')

        # 1. Check custom callable condition if provided
        if self.condition is not None:
            is_required = self.condition(other_field, form)
        # 2. Check if other_field's data matches expected values
        elif self.values is not None:
            is_required = other_field.data in self.values
        # 3. Default fallback: required if other_field has any truthy value
        else:
            is_required = bool(other_field.data)

        if is_required:
            InputRequired(message=self.message)(form, field)
        else:
            Optional()(form, field)


class AtLeastOneRequired:
    def __init__(self, message="Sélectionner au moins une option"):
        self.message = message

    def __call__(self, form, field):
        if len(field.data) == 0:
            InputRequired(self.message).__call__(form, field)


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select field that displays as a list of checkboxes.
    """

    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ProjectForm(FlaskForm):
    class Meta:
        csrf = True
        locales = ("fr_FR", "fr")

    id = IntegerField(
        "Identifiant du projet",
        description="Assigné automatiquement",
        default=None,
        render_kw={
            "min": "1",
            "type": "text",
            "inputmode": "numeric",
            "pattern": "[0-9]*",
            "readonly": "",
        },
        validators=[NumberRange(min=1, message="Identifiant invalide"), Optional()],
    )

    school_year = RadioField(
        "Année scolaire",
        choices=[("current", "Actuelle"), ("next", "Prochaine")],
        default="current",
        validators=[InputRequired()],
    )

    start_date = DateField(
        "Date ou début du projet",
        validators=[InputRequired()],
    )

    start_time = TimeField(
        "Heure",
        validators=[
            RequiredIf(
                "location",
                values=["outer", "trip"],
                message="L'heure est requise pour une sortie ou un voyage.",
            )
        ],
    )

    end_date = DateField(
        "Fin du projet",
        validators=[RequiredIf("location", values=["outer", "trip"], message="Date requise.")],
    )

    end_time = TimeField(
        "Heure",
        validators=[
            RequiredIf(
                "location",
                values=["outer", "trip"],
                message="L'heure est requise pour une sortie ou un voyage.",
            )
        ],
    )

    title = StringField(
        "Titre du projet",
        render_kw={"placeholder": "Titre du projet"},
        validators=[
            InputRequired(),
            Length(min=3, max=100),
            Regexp(r"^(?!\(Copie de\) ).*$", message="Mettre à jour le titre"),
        ],
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

    indicators = TextAreaField(
        "Indicateurs d'évaluation",
        description="Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet",
        render_kw={
            "placeholder": "Indicateurs d'évaluation retenus pour conserver, amender ou arrêter le projet"
        },
        validators=[Optional()],
    )

    members = SelectMultipleField(
        "Équipe pédagogique",
        description="Cliquer sur un nom pour sélectionner ou désélectionner une personne",
        coerce=int,
        validators=[InputRequired()],
    )

    priority = SelectField(
        "Axe et priorité du projet d'établissement",
        choices=choices["pe"],
        validators=[InputRequired()],
    )

    paths = MultiCheckboxField(
        "Parcours éducatifs",
        choices=choices["paths"],
        validators=[AtLeastOneRequired(message="Sélectionner au moins un parcours")],
    )

    skills = MultiCheckboxField(
        "Compétences transversales",
        choices=choices["skills"],
        validators=[AtLeastOneRequired(message="Sélectionner au moins une compétence")],
    )

    mode = RadioField(
        "Travail des élèves",
        choices=choices["mode"],
        description="Le travail des élèves sur ce projet est individuel, s'effectue en groupe, ou les deux",
        validators=[InputRequired(message="Choisir une option")],
    )

    divisions = SelectMultipleField(
        "Classes",
        choices=[],
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
        validators=[AtLeastOneRequired(message="Sélectionner au moins une classe")],
    )

    requirement = RadioField(
        "Participation",
        choices=[(k, v) for k, v in choices["requirement"].items()],
        description="Toute la classe participe au projet, seulement les élèves volontaires ou sélectionnés participent au projet (préciser alors la liste des élèves), ou la participation est libre (voir l'aide)",
        validators=[InputRequired(message="Choisir une option")],
    )

    nb_students = IntegerField(
        "Nombre d'élèves",
        description="Nombre d'élèves connu ou estimé participant au projet",
        validators=[InputRequired(), NumberRange(min=1, max=700)],
        render_kw={
            "min": "1",
            "max": "700",
        },
    )

    students = TextAreaField(
        "Liste des élèves",
        render_kw={
            "placeholder": "À remplir si la participation est optionnelle, avec un élève par ligne :\nClasse, Nom, Prénom",
        },
        description="Si la participation est optionnelle, préciser la liste des élèves avant la demande validation : un élève par ligne avec Classe, Nom, Prénom (séparés par une virgule, deux espaces ou une tabulation) ou copier / coller un tableau Google Sheets, LibreOffice Calc, MS Excel, etc.",
        validators=[
            RequiredIf(
                "requirement",
                condition=lambda other, form: (
                    other.data == "no" and form.status.data in ["ready", "adjust"]
                ),
                message="Préciser la liste des élèves",
            ),
        ],
    )

    location = RadioField(
        "Lieu",
        choices=[(k, v) for k, v in choices["location"].items()],
        description="Le projet se déroule en classe pendant les heures de cours habituelles, en dehors des heures de cours, en sortie scolaire, ou en voyage scolaire",
        validators=[InputRequired(message="Choisir une option")],
    )

    fieldtrip_address = TextAreaField(
        "Lieu et adresse de la sortie ou du voyage scolaire",
        render_kw={
            "placeholder": "À remplir pour une sortie scolaire : lieu et adresse de la sortie",
        },
        description="Préciser le lieu et l'adresse de la sortie scolaire",
        validators=[
            RequiredIf(
                "location",
                values=["outer", "trip"],
                message="L'adresse est requise pour une sortie ou un voyage scolaire.",
            ),
        ],
    )

    fieldtrip_ext_people = StringField(
        "Encadrement complémentaire (stagiaires et personnes extérieures au LFS)",
        render_kw={
            "placeholder": "Sophie Martin, Pierre Dupont (stagiaire)",
        },
        description="Indiquer, le cas échéant, le nom et prénom des stagiaires et des personnes extérieures au LFS encadrant la sortie (chaque personne séparée par une virgule)",
        validators=[
            Optional(),
            Regexp(
                prog_ext_people,
                message="Liste de personnes séparées par une virgule. Laisser vide sinon. Exemple: Sophie Martin, Pierre Dupont (stagiaire)",
            ),
            Length(max=200),
        ],
    )

    fieldtrip_impact = TextAreaField(
        "Incidence sur les autres cours et AES",
        render_kw={
            "placeholder": "Incidence sur les autres cours et AES",
        },
        description="Préciser, le cas échéant, l'incidence sur les autres cours et AES",
        validators=[Optional()],
    )

    link_t_1 = StringField(
        "Titre du lien",
        render_kw={"placeholder": "Titre descriptif"},
        validators=[
            Optional(),
            Length(max=50),
        ],
    )

    link_1 = StringField(
        "Lien",
        render_kw={"placeholder": "https://www.exemple.fr"},
        description="Site de référence, document partagé sur le Drive, etc.",
        validators=[
            Optional(),
            Regexp(prog_web_address, message="Cette adresse Web n'est pas valide"),
            Length(min=5, max=200),
        ],
    )

    link_t_2 = StringField(
        "Titre du lien",
        render_kw={"placeholder": "Titre descriptif"},
        validators=[
            Optional(),
            Length(max=50),
        ],
    )

    link_2 = StringField(
        "Lien",
        render_kw={"placeholder": "https://docs.google.com/..."},
        description="Site de référence, document partagé sur le Drive, etc.",
        validators=[
            Optional(),
            Regexp(prog_web_address, message="Cette adresse Web n'est pas valide"),
            Length(min=5, max=200),
        ],
    )

    link_t_3 = StringField(
        "Titre du lien",
        render_kw={"placeholder": "Titre descriptif"},
        validators=[
            Optional(),
            Length(max=50),
        ],
    )

    link_3 = StringField(
        "Lien",
        render_kw={"placeholder": "https://www.exemple.fr/dossier/document_partagé"},
        description="Site de référence, document partagé sur le Drive, etc.",
        validators=[
            Optional(),
            Regexp(prog_web_address, message="Cette adresse Web n'est pas valide"),
            Length(min=5, max=200),
        ],
    )

    link_t_4 = StringField(
        "Titre du lien",
        render_kw={"placeholder": "Titre descriptif"},
        validators=[
            Optional(),
            Length(max=50),
        ],
    )

    link_4 = StringField(
        "Lien",
        render_kw={"placeholder": "https://www.exemple.fr/"},
        description="Site de référence, document partagé sur le Drive, etc.",
        validators=[
            Optional(),
            Regexp(prog_web_address, message="Cette adresse Web n'est pas valide"),
            Length(min=5, max=200),
        ],
    )

    budget = RadioField(
        "Budget",
        choices=["Non", "Oui"],
        description="Le projet nécessite-t-il un budget ? Si oui, remplir les budgets nécessaires ci-dessous",
        validators=[InputRequired()],
    )

    budget_id = StringField(
        "Code budgétaire",
        description="Assigné par la gestion",
        default=None,
        render_kw={"type": "text", "readonly": ""},
        validators=[Optional(), Length(min=3, max=50)],
    )

    budget_hse_1 = IntegerField(
        "HSE",
        default=0,
        render_kw={"min": "0", "max": "70"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_hse_c_1 = TextAreaField(
        "Précisions sur le budget HSE",
        description="Préciser l'utilisation du budget HSE",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_hse_1", message="Préciser l'utilisation du budget HSE"),
        ],
    )

    budget_exp_1 = IntegerField(
        "Matériel",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_exp_c_1 = TextAreaField(
        "Précisions sur le budget matériel",
        description="Préciser l'utilisation du budget matériel (achat d'équipements et services)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_exp_1", message="Préciser l'utilisation du budget matériel"),
        ],
    )

    budget_trip_1 = IntegerField(
        "Frais de transport",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_trip_c_1 = TextAreaField(
        "Précisions sur le budget frais de transport",
        description="Préciser l'utilisation du budget pour les frais de transport",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_trip_1",
                message="Préciser l'utilisation du budget frais de transport",
            ),
        ],
    )

    budget_int_1 = IntegerField(
        "Frais d'intervention",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_int_c_1 = TextAreaField(
        "Précisions sur le budget frais d'intervention",
        description="Préciser l'utilisation du budget pour les frais d'intervention de personnes extérieures (prestation et déplacement)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_int_1",
                message="Préciser l'utilisation du budget pour les frais d'intervenants extérieurs",
            ),
        ],
    )

    budget_hse_2 = IntegerField(
        "HSE",
        default=0,
        render_kw={"min": "0", "max": "70"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_hse_c_2 = TextAreaField(
        "Précisions sur le budget HSE",
        description="Préciser l'utilisation du budget HSE",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_hse_2", message="Préciser l'utilisation du budget HSE"),
        ],
    )

    budget_exp_2 = IntegerField(
        "Matériel",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_exp_c_2 = TextAreaField(
        "Précisions sur le budget matériel",
        description="Préciser l'utilisation du budget matériel (achat d'équipements et services)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_exp_2", message="Préciser l'utilisation du budget matériel"),
        ],
    )

    budget_trip_2 = IntegerField(
        "Frais de transport",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_trip_c_2 = TextAreaField(
        "Précisions sur le budget frais de transport",
        description="Préciser l'utilisation du budget pour les frais de transport",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_trip_2",
                message="Préciser l'utilisation du budget frais de transport",
            ),
        ],
    )

    budget_int_2 = IntegerField(
        "Frais d'intervention",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(),
            NumberRange(min=0),
        ],
    )

    budget_int_c_2 = TextAreaField(
        "Précisions sur le budget frais d'intervention",
        description="Préciser l'utilisation du budget pour les frais d'intervention de personnes extérieures (prestation et déplacement)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_int_2",
                message="Préciser l'utilisation du budget pour les frais d'intervenants extérieurs",
            ),
        ],
    )

    is_recurring = RadioField(
        "Projet récurrent",
        choices=["Non", "Oui"],
        description="Ce projet sera-t-il proposé l'année prochaine ? Réponse non contraignante, utilisée pour établir une prévision du budget",
        validators=[InputRequired()],
    )

    status = RadioField(
        "Statut du projet",
        choices=choices["status"],
        default="draft",
        description="Le projet sera conservé comme brouillon ou soumis pour accord ou validation",
        validators=[InputRequired()],
    )

    submit = SubmitField("Enregistrer")

    def validate_end_date(form, field):
        if field.data < form.start_date.data:
            raise ValidationError("Invalide")

        if form.location.data == "outer" and field.data != form.start_date.data:
            raise ValidationError("Invalide pour une sortie scolaire")

        if form.location.data == "trip" and field.data == form.start_date.data:
            raise ValidationError("Invalide pour un voyage scolaire")

    def validate_end_time(form, field):
        if datetime.combine(form.end_date.data, field.data) < datetime.combine(
            form.start_date.data, form.start_time.data
        ):
            raise ValidationError("Invalide")

    def validate_students(form, field):
        if form.requirement.data == "no" and (
            form.status.data in ["ready", "adjust"] or field.data
        ):
            lines = field.data.splitlines()
            canonical_divisions = [div[0] for div in form.divisions.choices]
            for line_number, line in enumerate(lines, start=1):
                # split the line by comma, at least one tab or two spaces
                columns = re.split(r" *\t+ *| *, *|  +", line.strip())
                columns = [c for c in columns if c]

                if line.strip():
                    if len(form._fields.get("divisions").data) == 1:  # 2 columns (only one class)
                        # check if there are exactly 2 columns
                        if len(columns) == 1 or len(columns) > 3:
                            raise ValidationError(
                                f"Ligne {line_number}: deux colonnes sont attendues avec Nom, Prénom (séparés par une virgule, deux espaces ou une tabulation)"
                            )

                        if len(columns) == 2:
                            # check if columns contains valid names
                            for i in range(2):
                                if not re.match(r"^(\w[-' ]\w|\w)+$", columns[i].strip()):
                                    raise ValidationError(
                                        f"Ligne {line_number}: caractères invalides dans le nom ou le prénom"
                                    )
                        else:  # 3 columns
                            # check if the first column matches an actual division
                            if not valid_division(columns[0], canonical_divisions):
                                raise ValidationError(
                                    f"Ligne {line_number}: la classe n'est pas valide (consulter l'aide)"
                                )

                            # check if second and third columns contains valid names
                            for i in range(1, 3):
                                if not re.match(r"^(\w[-' ]\w|\w)+$", columns[i].strip()):
                                    raise ValidationError(
                                        f"Ligne {line_number}: caractères invalides dans le nom ou le prénom"
                                    )
                    else:  # 3 columns
                        # check if there are exactly 3 columns
                        if len(columns) != 3:
                            raise ValidationError(
                                f"Ligne {line_number}: trois colonnes sont attendues avec Classe, Nom, Prénom (séparés par une virgule, deux espaces ou une tabulation)"
                            )

                        # check if the first column matches an actual division
                        if not valid_division(columns[0], canonical_divisions):
                            raise ValidationError(
                                f"Ligne {line_number}: la classe n'est pas valide (consulter l'aide)"
                            )

                        # check if second and third columns contains valid names
                        for i in range(1, 3):
                            if not re.match(r"^(\w[-' ]\w|\w)+$", columns[i].strip()):
                                raise ValidationError(
                                    f"Ligne {line_number}: caractères invalides dans le nom ou le prénom"
                                )

    def validate_budget(form, field):
        budget = 0
        for budget_type in ["hse", "exp", "trip", "int"]:
            for budget_year in ["1", "2"]:
                budget += getattr(form, f"budget_{budget_type}_{budget_year}").data
        if field.data == "Oui":
            if budget == 0:
                raise ValidationError(
                    "Remplir au moins un budget ou indiquer « Non » si aucun budget n'est nécessaire"
                )
        else:
            if budget != 0:
                raise ValidationError("Répondre « Oui » ou annuler les budgets entrés ci-dessous")

    def validate_status(form, field):
        if form.school_year.data == "next" and field.data in ["ready", "adjust"]:
            raise ValidationError(
                "Une demande de validation est impossible pour un projet se déroulant l'année prochaine."
            )


class SelectProjectForm(FlaskForm):
    project_id = IntegerField(widget=HiddenInput(), validators=[InputRequired()])

    submit = SubmitField()


class CommentForm(FlaskForm):
    project_id = IntegerField(widget=HiddenInput(), validators=[InputRequired()])
    recipients = StringField(widget=HiddenInput(), validators=[Optional()])
    message = TextAreaField(
        "Ajouter un commentaire",
        description="Votre message sera enregistré sur la fiche projet et envoyé par e-mail à ",
        validators=[InputRequired()],
    )

    submit = SubmitField("Envoyer")


class RejectProjectForm(FlaskForm):
    message = TextAreaField(
        "Ajouter un commentaire",
        description="Le message sera enregistré sur la fiche projet et envoyé par e-mail à l'équipe pédagogique",
        render_kw={"placeholder": "Indiquer la motivation du refus..."},
        validators=[Optional()],
    )

    submit = SubmitField("Refuser")


class ProjectFilterForm(FlaskForm):
    filter = SelectField(
        choices=choices["filter"],
        default="LFS",
        validators=[InputRequired()],
    )

    submit = SubmitField("Filtrer")


class SelectYearsForm(FlaskForm):
    years = SelectField(
        validators=[InputRequired()],
    )

    submit = SubmitField("Sélectionner")


class LockForm(FlaskForm):
    lock = RadioField(
        "Enregistrement et mise à jour des projets dans la base",
        choices=["Ouvert", "Fermé"],
        validators=[InputRequired()],
    )

    submit = SubmitField("Appliquer")


class DownloadForm(FlaskForm):
    selection_mode = RadioField(
        "Sélection",
        choices=[("sy", "Année scolaire"), ("fy", "Année fiscale")],
        default="sy",
        validators=[InputRequired(message="Sélectionner une option")],
    )

    sy = SelectField("Année scolaire", choices=[], validators=[Optional()])
    fy = SelectField("Année fiscale", choices=[], validators=[Optional()])

    submit = SubmitField("Télécharger")


def create_schoolyear_config_form(levels):
    class SchoolYearConfigForm(FlaskForm):
        sy = StringField(widget=HiddenInput(), validators=[InputRequired(), Length(max=20)])

        sy_start = DateField("Début", validators=[InputRequired()])
        sy_end = DateField("Fin", validators=[InputRequired()])
        sy_auto = BooleanField(
            "Paramétrage automatique",
            default=True,
            description="Année scolaire du 1er septembre au 31 août de l'année suivante",
            validators=[Optional()],
        )
        submit = SubmitField("Enregistrer")

        def validate_sy_end(self, field):
            if field.data < self.sy_start.data:
                raise ValidationError("Date invalide : doit être postérieure à la date de début")
            if field.data > self.sy_start.data + relativedelta(months=15):
                raise ValidationError(
                    "Date invalide : doit être inférieure à 15 mois après la date de début"
                )

    # Add an IntegerField per level. Use safe field names (underscores only).
    for section in ["Lycée", "Collège", "Élémentaire", "Maternelle"]:
        for level_name in levels[section]:
            safe_field_name = f"level_{level_name.lower().replace(' ', '_')}"
            setattr(
                SchoolYearConfigForm,
                safe_field_name,
                IntegerField(
                    label=level_name,
                    default=0,
                    validators=[InputRequired(), NumberRange(min=0)],
                    render_kw={"min": 0, "value": 0},
                ),
            )

    return SchoolYearConfigForm


class MarkReadForm(FlaskForm):
    class Meta:
        csrf = True
        locales = ("fr_FR", "fr")

    submit = SubmitField("Tout marquer comme lu")


class PersonnelBaseForm(FlaskForm):
    """Base form containing common personnel fields and validations."""

    firstname = StringField("Prénom", validators=[InputRequired()])
    name = StringField("Nom", validators=[InputRequired()])
    email_username = StringField("Identifiant Email", validators=[InputRequired()])
    department = SelectField(
        "Département",
        choices=[(d, d) for d in choices.get("departments", [])],
        validators=[InputRequired()],
    )
    role = SelectField(
        "Rôle",
        choices=[
            ("user", "Utilisateur"),
            ("gestion", "Gestion"),
            ("direction", "Direction"),
            ("admin", "Administrateur"),
        ],
        default="user",
    )

    def validate_email_username(self, field):
        if not re.search(r"[a-z0-9]\.[a-z0-9]", field.data.lower()):
            raise ValidationError(
                "L'identifiant doit contenir un point, séparant des lettres ou des chiffres, généralement au format <kbd>prenom.nom</kbd>."
            )


class AddPersonnelForm(PersonnelBaseForm):
    submit = SubmitField("Ajouter le personnel")


class UpdatePersonnelForm(PersonnelBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if ("inactive", "Inactif") not in self.role.choices:
            self.role.choices.append(("inactive", "Inactif"))

    submit = SubmitField("Mettre à jour")


class RemovePersonnelForm(FlaskForm):
    personnel_id = SelectField(
        "Sélectionner le personnel", coerce=int, validators=[InputRequired()]
    )
    submit = SubmitField("Confirmer le départ")


class NotificationPreferencesForm(FlaskForm):
    # 1. New messages from teams
    notify_new_msg_team = MultiCheckboxField(
        "Messages des équipes pédagogiques",
        description="Nouveaux commentaires sur les fiches projet",
        choices=choices["level"],
        coerce=int,
    )

    # 2. Approval requests
    notify_approval_req = MultiCheckboxField(
        "Demandes d'accord et inclusion au budget",
        description="Nouvelles demandes d'accord et inclusion au budget",
        choices=choices["level"],
        coerce=int,
    )

    # 3. Validation requests
    notify_validation_req = MultiCheckboxField(
        "Demandes de validation",
        description="Nouvelles demandes de validation",
        choices=choices["level"],
        coerce=int,
    )

    # 4. Approved projects
    notify_approved = MultiCheckboxField(
        "Projets approuvés",
        description="Nouveaux projets approuvés et inclus au budget",
        choices=choices["level"],
        coerce=int,
    )

    # 5. Validated projects
    notify_validated = MultiCheckboxField(
        "Projets validés",
        description="Nouveaux projets validés",
        choices=choices["level"],
        coerce=int,
    )

    submit = SubmitField("Enregistrer")


class BudgetFilterForm(FlaskForm):
    filter = SelectField(
        choices=choices["filter-budget_id"],
        default="LFS",
        validators=[InputRequired()],
    )

    submit = SubmitField("Filtrer")


class ActionForm(FlaskForm):
    """An empty form used strictly for secure POST actions (CSRF protection)"""
