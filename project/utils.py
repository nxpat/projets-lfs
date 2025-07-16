from flask_login import current_user

from datetime import datetime
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_datetime

from .models import Personnel, User


def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))


def get_date_fr(date, withdate=True, withtime=False):
    if isinstance(date, str):
        try:
            # remove microseconds and time zone information, then convert to datetime
            date = datetime.strptime(date.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "None"
    if not date or str(date) == "NaT":
        return "None"
    elif not withdate:
        return format_datetime(date, format="H'h'mm", locale="fr_FR")
    elif withtime:
        return (
            format_datetime(date, format="EEE d MMM yyyy H'h'mm", locale="fr_FR")
            .capitalize()
            .removesuffix(" 0h00")
        )
    else:
        return format_date(date, format="EEE d MMM yyyy", locale="fr_FR").capitalize()


def get_project_dates(start_date, end_date):
    if end_date.date() == start_date.date():
        if end_date.time() == start_date.time():
            return get_date_fr(start_date, withtime=True)
        else:
            return f"{get_date_fr(start_date, withtime=False)} de {get_date_fr(start_date, withdate=False)} à {get_date_fr(end_date, withdate=False)}"
    else:
        return f"Du {get_date_fr(start_date, withtime=True)}<br>au {get_date_fr(end_date, withtime=True)}"


def get_name(pid=None, uid=None, option=None):
    if pid:
        personnel = Personnel.query.get(pid)
    elif uid:
        if isinstance(uid, str):
            uid = int(uid)
        personnel = Personnel.query.get(User.query.get(uid).pid)
    else:
        return "None"
    if personnel:
        if option and "s" in option:
            option = option.strip("s")
            if current_user.p.id == pid or current_user.id == uid:
                return "moi"
        if option == "nf":
            return f"{personnel.name} {personnel.firstname}"
        elif option == "f":
            return f"{personnel.firstname}"
        elif option == "n":
            return f"{personnel.name}"
        else:
            return f"{personnel.firstname} {personnel.name}"
    else:
        return "None"
