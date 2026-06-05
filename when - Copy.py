# File: urix/utils/when.py

from __future__ import annotations
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  
except Exception:  
    from pytz import timezone as ZoneInfo  # type: ignore[import]


def format_now(tz_name: str = "Asia/Kolkata") -> str:
    
    try:
        local = datetime.now(ZoneInfo(tz_name)) if isinstance(ZoneInfo, type) else ZoneInfo(tz_name).localize(datetime.now())
    except Exception:
        # Fallback to naive local time
        local = datetime.now()
    utc = datetime.utcnow()

    # Format
    local_str = local.strftime("%A, %d %B %Y • %I:%M:%S %p %Z")
    utc_str = utc.strftime("%Y-%m-%d %H:%M:%S UTC")

    return (
        f"# Current Date & Time\n\n"
        f"**Local ({tz_name}):** {local_str}\n\n"
        f"**UTC:** {utc_str}"
    )
