import os
import re
from urllib.parse import urlparse

import bleach
import markdown
from bs4 import BeautifulSoup

from ._version import __version__, __version_date__
from .project import choices, levels
from .utils import (
    division_name,
    division_names,
    get_date_fr,
    get_label,
    get_name,
    get_project_dates,
)

DOMAIN = os.getenv("DOMAIN")


def md_to_html(raw_markdown):
    """Converts raw markdown to sanitized HTML with Bulma classes."""
    if not raw_markdown:
        return ""

    html = markdown.markdown(raw_markdown, extensions=["extra", "nl2br"])
    soup = BeautifulSoup(html, "html.parser")

    mapping = {
        "h1": ["title", "is-5", "mb-2"],
        "h2": ["subtitle", "is-6"],
        "ul": ["mt-2"],
        "table": ["table", "is-striped", "is-hoverable"],
    }

    for tag, classes in mapping.items():
        for element in soup.find_all(tag):
            element["class"] = element.get("class", []) + classes

    for a in soup.find_all("a", href=True):
        parsed_url = urlparse(a["href"])
        if parsed_url.scheme in ["http", "https"] and parsed_url.netloc != DOMAIN:
            a["target"] = "_blank"
            a["rel"] = "noopener noreferrer"
            icon = soup.new_tag("i")
            icon["class"] = "si fa--arrow-up-right-from-square is-size-7 ml-1"
            icon["aria-hidden"] = "true"
            a.append(icon)

    allowed_tags = [
        "p",
        "br",
        "div",
        "strong",
        "em",
        "h1",
        "h2",
        "ul",
        "ol",
        "li",
        "code",
        "pre",
        "blockquote",
        "hr",
        "a",
        "i",
        "span",
        "img",
        "sup",
        "sub",
        "table",
        "tbody",
        "thead",
        "tr",
        "th",
        "td",
    ]
    allowed_attrs = {
        "*": ["class", "id", "aria-hidden"],
        "a": ["href", "title", "rel", "target"],
        "img": ["src", "alt", "title", "width", "height"],
    }

    return bleach.clean(str(soup), tags=allowed_tags, attributes=allowed_attrs)


def register_template_filters(app):
    """Registers global template filters and variables. Call this in your create_app()"""

    @app.template_filter("markdown")
    def markdown_filter(text):
        return md_to_html(text)

    @app.context_processor
    def utility_processor():
        # app_version string
        is_production = app.config.get("IS_PRODUCTION")
        env_string = "Production" if is_production else "Développement"
        is_sqlite = app.config.get("SQLALCHEMY_DATABASE_URI").startswith("sqlite:")
        db_string = "Lite" if is_sqlite else ""
        app_version = f"{__version__} - {__version_date__} - {env_string} {db_string}"

        def krw(v, currency=True):
            return f"{v:,} KRW".replace(",", " ") if currency else f"{v:,}".replace(",", " ")

        def get_validation_rank(status):
            ranks = {"draft": 0, "ready-1": 1, "ready": 3, "validated": 4, "rejected": 5}
            if status and status.startswith("validated-1"):
                return 2
            return ranks.get(status, 0)

        return {
            "get_date_fr": get_date_fr,
            "app_version": app_version,
            "get_name": get_name,
            "get_label": get_label,
            "levels": levels,
            "choices": choices,
            "division_name": division_name,
            "division_names": division_names,
            "get_project_dates": get_project_dates,
            "krw": krw,
            "regex_replace": re.sub,
            "regex_search": re.search,
            "get_validation_rank": get_validation_rank,
            "__version__": __version__,
            "is_production": is_production,
            "AUTHOR": os.getenv("AUTHOR"),
            "REFERENT_NUMERIQUE_EMAIL": os.getenv("REFERENT_NUMERIQUE_EMAIL"),
            "GITHUB_REPO": os.getenv("GITHUB_REPO"),
            "LFS_LOGO": os.getenv("LFS_LOGO"),
            "LFS_LOGO_REVERSE": os.getenv("LFS_LOGO_REVERSE"),
            "LFS_WEBSITE": os.getenv("LFS_WEBSITE"),
            "BOOMERANG_WEBSITE": os.getenv("BOOMERANG_WEBSITE"),
            "DOMAIN": os.getenv("DOMAIN"),
        }
