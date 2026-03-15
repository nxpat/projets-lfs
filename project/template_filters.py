from flask_login import current_user
import re
import markdown
import bleach
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from .utils import (
    get_date_fr,
    get_name,
    get_label,
    get_project_dates,
    division_name,
    division_names,
)
from .project import levels, choices
from ._version import __version__, __version_date__
import os

APP_DOMAIN = os.getenv("APP_DOMAIN")


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
        if parsed_url.scheme in ["http", "https"] and parsed_url.netloc != APP_DOMAIN:
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
        is_prod = app.config.get("FLASK_ENV") == "production"
        env_string = "Production" if is_prod else "Développement"
        app_version = f"{__version__} - {__version_date__} - {env_string}"

        def at_by(at_date, pid=None, uid=None, name=None, option="s"):
            c_uid = current_user.id if current_user.is_authenticated else None
            resolved_name = (
                name if name else get_name(pid=pid, uid=uid, option=option, current_user_uid=c_uid)
            )
            return f"{get_date_fr(at_date)} par {resolved_name}"

        def krw(v, currency=True):
            return f"{v:,} KRW".replace(",", " ") if currency else f"{v:,}".replace(",", " ")

        def get_validation_rank(status):
            ranks = {"draft": 0, "ready-1": 1, "ready": 3, "validated": 4, "rejected": 5}
            if status and status.startswith("validated-1"):
                return 2
            return ranks.get(status, 0)

        return dict(
            get_date_fr=get_date_fr,
            app_version=app_version,
            at_by=at_by,
            get_name=get_name,
            get_label=get_label,
            levels=levels,
            choices=choices,
            division_name=division_name,
            division_names=division_names,
            get_project_dates=get_project_dates,
            krw=krw,
            regex_replace=re.sub,
            regex_search=re.search,
            get_validation_rank=get_validation_rank,
            __version__=__version__,
            is_production=app.config.get("FLASK_ENV") == "production",
            AUTHOR=os.getenv("AUTHOR"),
            REFERENT_NUMERIQUE_EMAIL=os.getenv("REFERENT_NUMERIQUE_EMAIL"),
            GITHUB_REPO=os.getenv("GITHUB_REPO"),
            LFS_LOGO=os.getenv("LFS_LOGO"),
            LFS_WEBSITE=os.getenv("LFS_WEBSITE"),
            APP_BASE_URL=os.getenv("APP_BASE_URL"),
            BOOMERANG_WEBSITE=os.getenv("BOOMERANG_WEBSITE"),
        )
