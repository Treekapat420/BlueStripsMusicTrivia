from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone
import csv, os
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Score, User
from .utils.config import settings

def _week_key(dt: datetime) -> str:
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"

def _weekly_csv_path(week_key: str) -> str:
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"leaderboard_{week_key}.csv")

def export_weekly_csv(session: Session, week_key: str):
    q = session.execute(
        select(Score, User)
        .join(User, User.id == Score.user_id)
        .where(Score.week_key == week_key)
        .order_by(desc(Score.points))
    ).all()
    path = _weekly_csv_path(week_key)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank","tg_id","username","points","correct","wrong"])
        for idx, (s,u) in enumerate(q, start=1):
            w.writerow([idx, u.tg_id, u.username or "", s.points, s.correct, s.wrong])
    return path

def schedule_jobs(bot):
    sched = AsyncIOScheduler(timezone="UTC")
    # Export every Sunday 23:55 UTC by default (configurable by WEEKLY_RESET_DAY if desired)
    # For simplicity, keep Sunday cron here.
    sched.add_job(weekly_finalize, "cron", day_of_week="sun", hour=23, minute=55, args=[bot])
    sched.start()

async def weekly_finalize(bot):
    now = datetime.now(timezone.utc)
    wk = _week_key(now)
    with SessionLocal() as s:
        csv_path = export_weekly_csv(s, wk)
    # DM admins a notice
    for admin in getattr(bot, 'admin_ids', []):
        try:
            await bot.send_message(admin, f"Weekly export complete for {wk}: {csv_path}")
        except Exception:
            pass
