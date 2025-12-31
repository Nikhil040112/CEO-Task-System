import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, Form, HTTPException, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

from app.database import Base, engine, get_db
from app.models import Task, User
from app.utils import get_task_status, get_week_range
from app.email_utils import send_email, CEO_EMAIL
# -------------------------
# ENV
# -------------------------
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ENV = os.getenv("ENV", "development")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")

# -------------------------
# APP
# -------------------------
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=(ENV == "production")
)

Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="app/templates")

# -------------------------
# PASSWORD HASHING
# -------------------------
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# -------------------------
# AUTH HELPERS
# -------------------------
def require_login(request: Request):
    if "user_id" not in request.session:
        raise HTTPException(status_code=302, headers={"Location": "/login"})

def require_assistant(request: Request):
    if request.session.get("role") != "assistant":
        raise HTTPException(status_code=403, detail="Not allowed")

# -------------------------
# METRICS
# -------------------------
def compute_weekly_metrics(db: Session, week_start, week_end):
    tasks = db.query(Task).filter(
        Task.planned_datetime >= week_start,
        Task.planned_datetime <= week_end
    ).all()

    planned = len(tasks)
    completed = 0
    on_time = 0
    delayed = 0
    delay_hours = []
    high_priority_total = 0
    high_priority_delayed = 0

    for task in tasks:
        if task.priority == "High":
            high_priority_total += 1

        if task.actual_datetime:
            completed += 1
            if task.actual_datetime <= task.planned_datetime:
                on_time += 1
            else:
                delayed += 1
                delay = task.actual_datetime - task.planned_datetime
                delay_hours.append(delay.total_seconds() / 3600)
                if task.priority == "High":
                    high_priority_delayed += 1

    carryover = planned - completed
    completion_ratio = round((completed / planned) * 100, 1) if planned else 0
    on_time_ratio = round((on_time / completed) * 100, 1) if completed else 0
    delay_percentage = round((delayed / completed) * 100, 1) if completed else 0
    avg_delay = round(sum(delay_hours) / len(delay_hours), 2) if delay_hours else 0

    return {
        "planned": planned,
        "completed": completed,
        "completion_ratio": completion_ratio,
        "on_time_ratio": on_time_ratio,
        "delay_percentage": delay_percentage,  # ✅ NEW
        "avg_delay": avg_delay,
        "carryover": carryover,
        "high_priority_total": high_priority_total,
        "high_priority_delayed": high_priority_delayed
    }

# -------------------------
# LOGIN / LOGOUT
# -------------------------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials"}
        )

    request.session["user_id"] = user.id
    request.session["role"] = user.role

    return RedirectResponse("/dashboard", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

# -------------------------
# ROOT
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse("/dashboard", status_code=302)

# -------------------------
# DASHBOARD
# -------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    selected_date: str | None = None,
    db: Session = Depends(get_db)
):
    require_login(request)

    target_date = (
        datetime.strptime(selected_date, "%Y-%m-%d").date()
        if selected_date else datetime.today().date()
    )

    week_start, week_end = get_week_range(target_date)
    metrics = compute_weekly_metrics(db, week_start, week_end)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "selected_date": target_date,
            "week_start": week_start.date(),
            "week_end": week_end.date(),
            **metrics
        }
    )

@app.get("/dashboard/trends", response_class=HTMLResponse)
def dashboard_trends(request: Request, db: Session = Depends(get_db)):
    require_login(request)

    today = datetime.today().date()
    trends = []

    for i in range(5, -1, -1):
        target_date = today - timedelta(weeks=i)
        week_start, week_end = get_week_range(target_date)
        metrics = compute_weekly_metrics(db, week_start, week_end)

        trends.append({
            "week_start": week_start.date(),
            "week_end": week_end.date(),
            **metrics
        })

    return templates.TemplateResponse(
        "dashboard_trends.html",
        {"request": request, "trends": trends}
    )

# -------------------------
# TASKS
# -------------------------
@app.get("/tasks", response_class=HTMLResponse)
def view_tasks(request: Request, db: Session = Depends(get_db)):
    require_login(request)

    tasks = db.query(Task).filter(
        Task.actual_datetime.is_(None)
    ).order_by(Task.planned_datetime.asc()).all()

    task_data = [{
        "id": t.id,
        "title": t.title,
        "planned_datetime": t.planned_datetime,
        "priority": t.priority,
        "status": get_task_status(t)
    } for t in tasks]

    return templates.TemplateResponse("tasks.html",{"request": request,"tasks": task_data,"role": request.session.get("role")})


@app.get("/tasks/add", response_class=HTMLResponse)
def add_task_form(request: Request):
    require_login(request)
    return templates.TemplateResponse("add_tasks.html", {"request": request})

@app.post("/tasks/create")
def create_task(
    request: Request,
    title: str = Form(...),
    planned_datetime: datetime = Form(...),
    description: str = Form(""),
    priority: str = Form("Medium"),
    db: Session = Depends(get_db)
):
    require_login(request)

    task = Task(
        title=title,
        description=description,
        planned_datetime=planned_datetime,
        priority=priority
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 📧 EMAIL NOTIFICATION
    send_email(
        to_email=CEO_EMAIL,  # CEO gets notified
        subject="🆕 New Task Added",
        html_body=f"""
        <h3>New Task Created</h3>
        <p><b>Title:</b> {task.title}</p>
        <p><b>Planned Time:</b> {task.planned_datetime}</p>
        <p><b>Priority:</b> {task.priority}</p>
        """
    )

    return RedirectResponse("/tasks", status_code=302)

@app.post("/tasks/{task_id}/done")
def mark_task_done(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db)
):
    require_login(request)

    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(status_code=404)

    task.actual_datetime = datetime.now()
    db.commit()

    return RedirectResponse("/tasks", status_code=302)

@app.post("/tasks/{task_id}/reschedule")
def reschedule_task(
    request: Request,
    task_id: int,
    new_planned_datetime: datetime = Form(...),
    db: Session = Depends(get_db)
):
    require_login(request)
    require_assistant(request)

    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(status_code=404)

    task.planned_datetime = new_planned_datetime
    db.commit()

    return RedirectResponse("/tasks", status_code=302)

@app.get("/tasks/completed", response_class=HTMLResponse)
def completed_tasks(request: Request, db: Session = Depends(get_db)):
    require_login(request)

    tasks = db.query(Task).filter(
        Task.actual_datetime.isnot(None)
    ).order_by(Task.actual_datetime.desc()).all()

    completed = []
    for t in tasks:
        status = get_task_status(t)
        delay = None
        if status == "Delayed":
            delay = round(
                (t.actual_datetime - t.planned_datetime).total_seconds() / 3600,
                2
            )

        completed.append({
            "title": t.title,
            "planned_datetime": t.planned_datetime,
            "actual_datetime": t.actual_datetime,
            "status": status,
            "delay_hours": delay
        })

    return templates.TemplateResponse(
        "completed_tasks.html",
        {"request": request, "tasks": completed}
    )

CRON_SECRET = os.getenv("CRON_SECRET")

@app.get("/cron/check-overdue")
def check_overdue_tasks(
    x_cron_secret: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Triggered by GitHub Actions (cron job)
    Sends email reminders for overdue tasks
    """

    # 🔐 Security check
    if CRON_SECRET and x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    now = datetime.now()

    # 🔍 Find overdue tasks
    overdue_tasks = db.query(Task).filter(
        Task.actual_datetime.is_(None),
        Task.planned_datetime < now
    ).all()

    # 📧 Send emails
    for task in overdue_tasks:
        send_email(
            to_email=CEO_EMAIL,
            subject="⚠️ Overdue Task Reminder",
            html_body=f"""
            <h3>Overdue Task</h3>
            <p><b>Title:</b> {task.title}</p>
            <p><b>Planned Time:</b> {task.planned_datetime}</p>
            <p><b>Priority:</b> {task.priority}</p>
            <p>Please review and take action.</p>
            """
        )

    return {
        "status": "ok",
        "overdue_tasks": len(overdue_tasks)
    }
