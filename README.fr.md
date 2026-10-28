[🇬🇧 View in English](readme.md)

# Projets LFS

## Présentation

**Projets LFS** est la plateforme de gestion des projets pédagogiques du Lycée Français de Séoul (LFS). Développée en Python avec le framework Flask, elle offre à l'administration et aux équipes pédagogiques un espace collaboratif centralisé pour créer, valider et suivre les projets et leurs budgets.

## Fonctionnalités

- **Gestion des rôles et accès :**
  - *Enseignants :* Création, duplication, soumission et suivi de l'historique de leurs projets.
  - *Direction & Gestionnaires :* Examen, validation, gestion des codes budgétaires et supervision globale.
- **Fiches projets complètes :** Saisie centralisée (objectifs pédagogiques, compétences, groupes d'élèves, budget par année civile, informations logistiques).
- **Sorties scolaires :** Génération automatique de fiches de sortie formatées (ex. : pour l'ambassade).
- **Outils collaboratifs :** Messagerie intégrée à chaque projet et notifications automatiques par e-mail lors des événements clés.
- **Exploration et analyse :** 
  - Recherche et filtrage avancés (année, département) avec visibilité adaptée au rôle.
  - Tableaux de bord statistiques et graphiques interactifs (projet d'établissement et chronologie).
  - Gestion budgétaire avec export des bases de données vers un tableur.
  - Tableau de bord pour la gestion administrative.
- **Authentification :** Connexion classique (identifiant/mot de passe) ou via Google OAuth (SSO).

## Technologies utilisées

- **Backend :** Python 3.10+, Flask, SQLAlchemy (Flask-Login, Flask-WTF, Flask-Babel), Authlib (OAuth), Google API, Pandas, Plotly.
- **Frontend :** HTML/Jinja rendu côté serveur, framework Bulma CSS, JavaScript, Plotly (graphiques).
- **Base de données :** SQLite ou MySQL/MariaDB.

## Copies d'écran (à venir)

![Login](docs/images/login.png)
![Project Form](docs/images/project-form.png)
![Project List](docs/images/project-list.png)
![Dashboard](docs/images/dashboard.png)
![Data analysis](docs/images/data-analysis.png)
![Budget](docs/images/budget.png)
![Manage budget ids](docs/images/manage-budget-ids.png)
![Profile](docs/images/profile.png)
![Help](docs/images/help.png)

## Installation et environnement de développement

### Prérequis

- Python 3.10+
- Git
- Modules listés dans `requirements.txt`

### Linux / macOS

Depuis la racine du dépôt :

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

export FLASK_ENV=development
export FLASK_APP=project
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export DEV_DATABASE_URI=sqlite:///db.sqlite
export USE_GMAIL_SERVICE=False
export APP_EMAIL=dev@etablissement.fr

export FLASK_DEBUG=1
flask run --debug

```

### Windows (PowerShell)

Depuis la racine du dépôt :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

$env:FLASK_ENV = "development"
$env:FLASK_APP = "project"
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
$env:DEV_DATABASE_URI = "sqlite:///db.sqlite"
$env:USE_GMAIL_SERVICE = "False"
$env:APP_EMAIL = "dev@etablissement.fr"

$env:FLASK_DEBUG = 1
flask run --debug

```

### Notes de configuration

* **Clé secrète :** La `SECRET_KEY` générée par les commandes ci-dessus est temporaire. En production, utiliser une variable d'environnement fixe et sécurisée.
* **Comptes utilisateurs :** Les personnels autorisés doivent être enregistrés en base de données avant de pouvoir se connecter.
* **Google SSO :** Nécessite de configurer `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` et l'URI de redirection appropriée sur Google Cloud Console.
* **Notifications Gmail :** Le service est activé par défaut (sauf si `USE_GMAIL_SERVICE=False`). Il requiert `CLIENT_SECRET_FILE` et un jeton API Google (`TOKEN_FILE`) valides. **Ne versionner jamais ces identifiants.**

## Déploiement en production

Déployer l'application derrière un serveur WSGI de production (ex: Gunicorn, uWSGI) ou sur une plateforme d'hébergement compatible WSGI comme PythonAnywhere. N'utiliser jamais le serveur de développement natif (`flask run`) en production.
