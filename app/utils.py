from datetime import datetime, date, timedelta

def get_task_status(task):
    now = datetime.now()

    if task.actual_datetime:
        if task.actual_datetime <= task.planned_datetime:
            return "Completed"
        return "Delayed"

    if now < task.planned_datetime:
        return "Upcoming"

    return "Pending"


def get_week_range(target_date=None):
    if not target_date:
        target_date = date.today()

    # Week starts on Monday
    start_date = target_date - timedelta(days=target_date.weekday())
    end_date = start_date + timedelta(days=6)

    # Convert to datetime range
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    return start_datetime, end_datetime