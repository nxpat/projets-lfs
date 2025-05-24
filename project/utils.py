from datetime import datetime
from zoneinfo import ZoneInfo

def get_datetime():
    return datetime.now(tz=ZoneInfo("Asia/Seoul"))