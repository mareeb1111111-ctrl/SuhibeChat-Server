from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from database import get_db
import models
from auth import get_current_user

router = APIRouter(prefix="/api/stats", tags=["Statistics"])

@router.get("/messages")
def get_message_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    daily = db.query(models.Message).filter(models.Message.created_at >= today).count()
    weekly = db.query(models.Message).filter(models.Message.created_at >= start_of_week).count()
    monthly = db.query(models.Message).filter(models.Message.created_at >= start_of_month).count()
    
    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly
    }

@router.get("/users")
def get_users_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    daily = db.query(models.User).filter(models.User.last_login >= today).count()
    weekly = db.query(models.User).filter(models.User.last_login >= start_of_week).count()
    monthly = db.query(models.User).filter(models.User.last_login >= start_of_month).count()
    
    return {
        "daily_active": daily,
        "weekly_active": weekly,
        "monthly_active": monthly
    }
