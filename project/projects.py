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
    NumberRange,
)
from markupsafe import Markup

from datetime import datetime

import re

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
choices["secondary"] = [
    "Arts et technologie",
    "Langues",
    "Lettres",
    "Mathématiques NSI",
    "Sciences",
    "Sciences humaines",
    "Sport",
]

choices["primary"] = [
    "Élémentaire",
    "Maternelle",
]

choices["departments"] = (
    choices["secondary"] + choices["primary"] + ["ASEM"] + ["Vie Scolaire"] + ["Administration"]
)

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
}

choices["budgets"] = [b + f"_{n}" for b in choices["budget"] for n in [1, 2]]

# choix du statut des projets
choices["status"] = [
    ("draft", "Brouillon"),
    ("ready-1", "Demande d'accord et inclusion au budget"),
    ("adjust", "Ajuster"),
    ("ready", "Demande de validation"),
]

choices["school_year"] = [("current", "Actuelle"), ("next", "Prochaine")]

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

# sections
sections = ["secondary", "elementary", "kindergarten"]

# ordered levels by section
# canonical division names are obtained by adding the division letter ("A", "B", etc.) to the level
levels = {}
levels["secondary"] = ("0", "1", "2", "3", "4", "5", "6")
levels["elementary"] = ("cm2", "cm1", "ce2", "ce1", "cp")
levels["kindergarten"] = ("gs", "msgs", "ms", "psms", "ps")
levels["lfs"] = levels["secondary"] + levels["elementary"] + levels["kindergarten"]

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
        re.compile(r"(gs|msgs|ms|psms|ps) *([a-d])?", re.IGNORECASE),
        r"\1",
        r"\2",
    ),  # maternelle
    (re.compile(r"ms/gs *([a-d])?", re.IGNORECASE), "msgs", r"\1"),  # maternelle
    (re.compile(r"ps/ms *([a-d])?", re.IGNORECASE), "psms", r"\1"),  # maternelle
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
    """
    Validator which makes a field required if another field is set
    """

    field_flags = ("requiredif",)

    def __init__(self, other_field_name, message=None):
        self.other_field_name = other_field_name
        self.message = message

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)
        if not other_field:
            raise Exception(f'no field named "{self.other_field_name}" in form')
        if self.other_field_name.startswith("budget_") and other_field.data:
            InputRequired(self.message).__call__(form, field)
        elif self.other_field_name == "location" and other_field.data in [
            "outer",
            "trip",
        ]:
            InputRequired(self.message).__call__(form, field)
        elif (self.other_field_name == "requirement" and other_field.data == "no") and (
            form._fields.get("status").data in ["ready", "adjust"]
        ):
            InputRequired(self.message).__call__(form, field)
        else:
            Optional(self.message).__call__(form, field)


class BulmaCheckboxes(widgets.ListWidget):
    def __call__(self, field, **kwargs):
        kwargs.setdefault("id", field.id)
        html = [f"<div class='checkboxes' id='{field.id}'>"]
        for subfield in field:
            html.append(f"<label class='checkbox'>{subfield()} {subfield.label.text}</label>")
        html.append("</div>")
        return Markup("".join(html))


class BulmaMultiCheckboxField(SelectMultipleField):
    widget = BulmaCheckboxes()
    option_widget = widgets.CheckboxInput()


class AtLeastOneRequired(object):
    def __call__(self, form, field):
        if len(field.data) == 0:
            raise ValidationError("Sélectionner au moins une option")


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
        choices=choices["school_year"],
        default="current",
        validators=[InputRequired()],
    )

    start_date = DateField(
        "Date ou début du projet",
        description="L'heure est optionnelle, sauf pour les sorties scolaires",
        validators=[InputRequired()],
    )

    start_time = TimeField(
        "Heure",
        validators=[RequiredIf("location")],
    )

    end_date = DateField(
        "Fin du projet",
        validators=[RequiredIf("location")],
    )

    end_time = TimeField(
        "Heure",
        validators=[RequiredIf("location")],
    )

    title = StringField(
        "Titre du projet",
        description="100 caractères maximum",
        render_kw={"placeholder": "Titre du projet"},
        validators=[
            InputRequired(),
            Length(min=3, max=100),
            Regexp(r"^(?!\(Copie de\) ).*$", message="Vous devez modifier le titre"),
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
        validators=[Optional(), Length(max=1000)],
    )

    members = SelectMultipleField(
        "Équipe pédagogique associée au projet",
        description="Appuyer sur <kbd>Ctrl</kbd> ou <kbd>Shift</kbd>, puis cliquer pour sélectionner plusieurs personnels",
        validators=[InputRequired()],
    )

    priority = SelectField(
        "Axe et priorité du projet d'établissement",
        choices=choices["pe"],
        validators=[InputRequired()],
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

    mode = RadioField(
        "Travail des élèves",
        choices=["Individuel", "En groupe", "Individuel et en groupe"],
        description="Le travail des élèves sur ce projet est individuel, s'effectue en groupe, ou les deux",
        validators=[InputRequired(message="Choisir une option")],
    )

    divisions = BulmaMultiCheckboxField(
        "Classes",
        validators=[AtLeastOneRequired()],
    )

    requirement = RadioField(
        "Participation",
        choices=[("yes", "Toute la classe"), ("no", "Optionnelle"), ("free", "Libre")],
        description="Toute la classe participe au projet, seulement les élèves volontaires ou sélectionnés participent au projet (préciser alors la liste des élèves), ou la participation est libre (voir l'aide)",
        validators=[InputRequired(message="Choisir une option")],
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

    students = TextAreaField(
        "Liste des élèves",
        render_kw={
            "placeholder": "À remplir si la participation est optionnelle, avec un élève par ligne :\nClasse, Nom, Prénom",
        },
        description="Si la participation est optionnelle, préciser la liste des élèves avant la demande validation : un élève par ligne avec Classe, Nom, Prénom (séparés par une virgule, deux espaces ou une tabulation) ou copier / coller un tableau Google Sheets, LibreOffice Calc, MS Excel, etc.",
        validators=[
            RequiredIf("requirement", "Préciser la liste des élèves"),
        ],
    )

    location = RadioField(
        "Lieu",
        choices=[
            ("in", "LFS, en classe"),
            ("out", "LFS, en dehors de la classe"),
            ("outer", "Sortie scolaire"),
            ("trip", "Voyage scolaire"),
        ],
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
            RequiredIf("location", "Préciser le lieu et l'adresse de la sortie scolaire"),
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
        "Texte du lien",
        render_kw={"placeholder": "Titre descriptif"},
        description="50 caractères maximum",
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
        "Texte du lien",
        render_kw={"placeholder": "Titre descriptif"},
        description="50 caractères maximum",
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
        "Texte du lien",
        render_kw={"placeholder": "Titre descriptif"},
        description="50 caractères maximum",
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
        "Texte du lien",
        render_kw={"placeholder": "Titre descriptif"},
        description="50 caractères maximum",
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

    budget_hse_1 = IntegerField(
        "HSE",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Nombre supérieur ou égal à 0"),
            RequiredIf("budget_hse_c_1", "Indiquer un nombre"),
        ],
    )

    budget_hse_c_1 = TextAreaField(
        "Précisions sur le budget HSE",
        description="Préciser l'utilisation du budget HSE",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_hse_1", "Préciser l'utilisation du budget HSE"),
        ],
    )

    budget_exp_1 = IntegerField(
        "Matériel",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Montant supérieur ou égal à 0"),
            RequiredIf("budget_exp_c_1", "Indiquer un montant"),
        ],
    )

    budget_exp_c_1 = TextAreaField(
        "Précisions sur le budget matériel",
        description="Préciser l'utilisation du budget matériel (achat d'équipements et services)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_exp_1", "Préciser l'utilisation du budget matériel"),
        ],
    )

    budget_trip_1 = IntegerField(
        "Frais de transport",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Montant supérieur ou égal à 0"),
            RequiredIf("budget_trip_c_1", "Indiquer un montant"),
        ],
    )

    budget_trip_c_1 = TextAreaField(
        "Précisions sur le budget frais de transport",
        description="Préciser l'utilisation du budget pour les frais de transport",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_trip_1",
                "Préciser l'utilisation du budget frais de transport",
            ),
        ],
    )

    budget_int_1 = IntegerField(
        "Frais d'intervention",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Montant supérieur ou égal à 0"),
            RequiredIf("budget_int_c_1", "Indiquer un montant"),
        ],
    )

    budget_int_c_1 = TextAreaField(
        "Précisions sur le budget frais d'intervention",
        description="Préciser l'utilisation du budget pour les frais d'intervention de personnes extérieures (prestation et déplacement)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_int_1",
                "Préciser l'utilisation du budget frais d'intervention",
            ),
        ],
    )

    budget_hse_2 = IntegerField(
        "HSE",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Nombre supérieur ou égal à 0"),
            RequiredIf("budget_hse_c_2", "Indiquer un nombre"),
        ],
    )

    budget_hse_c_2 = TextAreaField(
        "Précisions sur le budget HSE",
        description="Préciser l'utilisation du budget HSE",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_hse_2", "Préciser l'utilisation du budget HSE"),
        ],
    )

    budget_exp_2 = IntegerField(
        "Matériel",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Montant supérieur ou égal à 0"),
            RequiredIf("budget_exp_c_2", "Indiquer un montant"),
        ],
    )

    budget_exp_c_2 = TextAreaField(
        "Précisions sur le budget matériel",
        description="Préciser l'utilisation du budget matériel (achat d'équipements et services)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf("budget_exp_2", "Préciser l'utilisation du budget matériel"),
        ],
    )

    budget_trip_2 = IntegerField(
        "Frais de transport",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Montant supérieur ou égal à 0"),
            RequiredIf("budget_trip_c_2", "Indiquer un montant"),
        ],
    )

    budget_trip_c_2 = TextAreaField(
        "Précisions sur le budget frais de transport",
        description="Préciser l'utilisation du budget pour les frais de transport",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_trip_2",
                "Préciser l'utilisation du budget frais de transport",
            ),
        ],
    )

    budget_int_2 = IntegerField(
        "Frais d'intervention",
        default=0,
        render_kw={"min": "0"},
        validators=[
            InputRequired(message="Montant supérieur ou égal à 0"),
            RequiredIf("budget_int_c_2", "Indiquer un montant"),
        ],
    )

    budget_int_c_2 = TextAreaField(
        "Précisions sur le budget frais d'intervention",
        description="Préciser l'utilisation du budget pour les frais d'intervention de personnes extérieures (prestation et déplacement)",
        render_kw={"placeholder": "À remplir si un budget est indiqué"},
        validators=[
            RequiredIf(
                "budget_int_2",
                "Préciser l'utilisation du budget frais d'intervention",
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
                print(columns)

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


class SelectProjectForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])

    submit = SubmitField()


class CommentForm(FlaskForm):
    project = IntegerField(widget=HiddenInput(), validators=[InputRequired()])
    recipients = StringField(widget=HiddenInput(), validators=[Optional()])
    message = TextAreaField(
        "Ajouter un commentaire",
        description="Votre message sera affiché ici sur la fiche projet et envoyé par e-mail à ",
        validators=[InputRequired()],
    )

    submit = SubmitField("Envoyer")


class ProjectFilterForm(FlaskForm):
    filter = SelectField(
        choices=choices["filter"],
        default="LFS",
        validators=[InputRequired()],
    )

    submit = SubmitField("Filtrer")


class SelectSchoolYearForm(FlaskForm):
    sy = SelectField(
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
    file = StringField(
        "Télécharger la base des projets au format Excel",
        widget=HiddenInput(),
        validators=[InputRequired()],
    )

    submit = SubmitField("Télécharger")


class SetSchoolYearForm(FlaskForm):
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

    sy_submit = SubmitField("Paramétrer")

    def validate_sy_end(self, field):
        if field.data < self.sy_start.data:
            raise ValidationError("Date incorrecte")
