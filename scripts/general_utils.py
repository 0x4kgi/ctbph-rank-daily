from datetime import datetime, timedelta, timezone


def timestamp_utc_offset(
        timestamp: float,
        time_offset: int,
        time_format: str,
) -> str:
    dt_object = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    dt_timezone = timezone(timedelta(hours=time_offset))
    dt_timezone = dt_object.astimezone(dt_timezone)
    formatted_time = dt_timezone.strftime(time_format)

    return formatted_time
