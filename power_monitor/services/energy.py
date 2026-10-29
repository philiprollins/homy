from datetime import datetime, timedelta, timezone


def integrate(previous, current, max_gap):
    """Trapezoidal integration of positive and negative power, split at UTC midnight and zero crossings."""
    start, end = previous.timestamp, current.timestamp
    seconds = (end - start).total_seconds()
    p0, p1 = previous.power_w, current.power_w
    if seconds <= 0 or seconds > max_gap or p0 is None or p1 is None:
        return []
    points = [0.0, seconds]
    midnight = datetime.combine(start.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    while midnight < end:
        points.append((midnight - start).total_seconds())
        midnight += timedelta(days=1)
    if p0 * p1 < 0:
        points.append(seconds * -p0 / (p1 - p0))
    points.sort()
    result = []
    for a, b in zip(points, points[1:]):
        pa = p0 + (p1 - p0) * a / seconds
        pb = p0 + (p1 - p0) * b / seconds
        kwh = (pa + pb) / 2 * (b - a) / 3_600_000
        result.append(((start + timedelta(seconds=a)).date().isoformat(), max(kwh, 0), max(-kwh, 0)))
    return result
