# Architecture

## Application Structure

```text
.
├── config.py                 # Environment loading and dev/production settings
├── requirements.txt          # Pinned Python dependencies
├── run.sh                    # Existing Linux-oriented Flask launcher
└── project/
    ├── __init__.py           # create_app(), extensions, blueprint registration
    ├── auth.py               # Login, signup, Google OAuth, logout
    ├── babel.py              # Locale configuration
    ├── models.py             # SQLAlchemy models and relationships
    ├── project.py            # Forms, project choices, and workflow form logic
    ├── routes/
    │   ├── core.py           # Profile, help, preferences, delegations
    │   ├── projects.py       # Project lifecycle, listing, details, analysis
    │   └── admin.py          # Dashboard, budgets, personnel, school years
    ├── templates/            # Jinja pages and partials
    ├── static/
    │   ├── assets/           # Site assets
    │   ├── js/               # Page behavior and bundled Plotly/Mark libraries
    │   └── styles/           # Bulma and application styles
    ├── data/                 # Application data and bundled sample/export files
    ├── data.py               # Analysis data preparation
    ├── graphs.py             # Plotly chart generation
    ├── utils.py              # Shared query, school-year, and formatting helpers
    ├── decorators.py         # Database-lock access guard
    ├── errors.py             # Error handling and project lookup helpers
    ├── notifications.py      # Notification construction and dispatch
    ├── google_api_service.py # Google API credential and service setup
    ├── gmail_api_client.py   # Gmail message sending
    ├── pdf_generator.py      # Project/field-trip PDF generation
    ├── registration.py       # Authentication forms
    ├── template_filters.py   # Jinja filters and template context values
    └── profiler.py           # Optional development query profiler
```

`create_app()` in [`project/__init__.py`](project/__init__.py) reads `FLASK_ENV` (defaulting to `production`), loads `ProdConfig` or `DevConfig`, initializes CSRF protection, SQLAlchemy, Babel, Flask-Login, template filters, and error handlers, then registers four blueprints. It calls `db.create_all()` only outside production. The same module initializes Gmail integration at import time unless `USE_GMAIL_SERVICE` is set to `False` or `0`.

[`config.py`](config.py) loads a root `.env` file. Development defaults to `sqlite:///db.sqlite`; production requires `PROD_DATABASE_URI`.

## Database Model

The schema is declared in [`project/models.py`](project/models.py) with Flask-SQLAlchemy and SQLAlchemy mapped relationships.

| Model | Purpose and relationships |
| --- | --- |
| `Personnel` | Directory record for an authorized school staff member, including email, department, and role. Has an optional one-to-one `User` and project memberships through `ProjectMember`. |
| `User` | Login account and per-user JSON preferences/unread-message data. Links one-to-one to `Personnel`; owns projects through `Project.uid`; has comments through `ProjectComment`. |
| `Project` | Main project record: owner, school year, dates, objectives, divisions/students, field-trip details, budget values, status, and modification/validation actors. Has one-to-many members, comments, and history entries. |
| `ProjectMember` | Association between `Project` and `Personnel`, with a composite project/personnel key and optional team role/department. |
| `ProjectHistory` | Status and selected project/budget snapshots, linked to a project and the user who recorded the change. |
| `ProjectComment` | Comment message and timestamp, optionally linked to a project and user. |
| `Dashboard` | Application-wide lock state and dashboard messages. Routes use it to control project editing and maintenance access. |
| `SchoolYear` | School-year boundaries and JSON configuration for divisions and pedagogical data. Projects store the school-year label as a string rather than a declared foreign key. |
| `QueuedAction` | Optional user-linked queued action with status, type, timestamp, and JSON parameters/options. |

The project creator, last modifier, and validator are all represented by foreign keys to `User`. Project members are personnel records, not user records, so a team member does not necessarily have a login. Project deletion cascades through its member, comment, and history relationships as configured on `Project`.

## Routing and Access

Blueprints are registered in [`project/__init__.py`](project/__init__.py). Login requirements and role checks are enforced by route decorators and handler logic.

| Blueprint | Main routes | Responsibility and access notes |
| --- | --- | --- |
| `auth` | `/login`, `/signup`, `/google_login`, `/authorize`, `/logout` | Development uses local password login/signup. Production login and signup redirect to Google OAuth. OAuth accounts must match a pre-existing, non-inactive `Personnel` record. Signup is subject to database-lock checks. |
| `core` | `/`, `/profile`, `/profile/notifications`, `/profile/delegations`, `/help`, `/language=<language>`, `/set_theme` | Profile and help require login. Notification preferences are limited to `gestion` and `direction`; delegation management is limited to `direction`. |
| `projects` | `/projects`, `/form`, `/form/<id>/<req>`, `/project/<id>`, `/project/validate/<id>`, `/project/devalidate/<id>`, `/project/reject/<project_id>`, `/project/delete/<id>`, `/project/comment/add`, `/api/history/<id>`, `/api/budget/<id>`, `/project/print/<id>`, `/data` | Project listing, details, forms, comments, history, print views, and data analysis require login. Form edits are restricted to the creator or a project member and are affected by database lock and project status. Direction validates/rejects projects; devalidation is available to direction or delegated gestion users. Deletion is restricted to the creator and disallowed for validated projects. |
| `admin` | `/dashboard`, `/budget`, `/manage_budgets`, `/dashboard/personnels`, `/personnel/add`, `/personnel/update/<pid>`, `/personnel/remove`, `/dashboard/sy`, `/download`, `/api/project/<project_id>/update-budget` | Dashboard and budget pages require management/direction/admin roles, with additional permission checks for personnel and budget-ID changes. Gestion users need delegation to edit budget IDs; direction can manage them directly. The dashboard also controls database availability and school-year settings. |

The project workflow is represented by status values such as `draft`, `ready-1`, `validated-1`, `ready`, `validated`, `validated-10`, and `rejected`. The exact transitions depend on current school year, user role/delegations, project state, and database lock.
