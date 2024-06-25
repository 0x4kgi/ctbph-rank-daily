import math
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


def simplify_number(num):
    """
    ChatGPT code, I got too lazy.

    Simplifies a number by adding appropriate suffixes (k, M, B, T) for thousands, millions, billions, and trillions.

    Parameters:
    num (int or float): The number to simplify.

    Returns:
    str: The simplified number with the appropriate suffix.
    """
    suffixes = ['', 'k', 'M', 'B', 'T']
    magnitude = 0

    # Determine the magnitude
    while abs(num) >= 1000 and magnitude < len(suffixes) - 1:
        magnitude += 1
        num /= 1000.0

    # Format the number with the appropriate suffix
    if magnitude == 0:
        return f"{num:.0f}"
    else:
        return f"{num:.2f}{suffixes[magnitude]}"


def get_pp_pb_place_from_weight(weight: float) -> int:
    base = 0.95
    factor = 100
    ln_base = math.log(base)
    ln_target = math.log(weight / factor)
    n_minus_1 = ln_target / ln_base
    n = n_minus_1 + 1
    return round(n)
