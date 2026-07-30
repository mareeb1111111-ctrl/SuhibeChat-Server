from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import schemas
import models
from auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@router.post("/register")
def register_device(data: schemas.NotificationRegister, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.NotificationToken).filter(models.NotificationToken.fcm_token == data.fcm_token).first()
    if existing:
        if existing.user_id != current_user.id:
            existing.user_id = current_user.id
            db.commit()
        return {"success": True, "message": "Token updated"}
        
    token = models.NotificationToken(
        user_id=current_user.id,
        fcm_token=data.fcm_token,
        device_type=data.device_type
    )
    db.add(token)
    db.commit()
    return {"success": True, "message": "Token registered"}

@router.post("/send")
def send_notification(user_id: int, title: str, body: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # In a real app, this would use firebase-admin
    # For now we just log it
    tokens = db.query(models.NotificationToken).filter(models.NotificationToken.user_id == user_id).all()
    if not tokens:
        return {"success": False, "message": "المستخدم ليس لديه أجهزة مسجلة"}
        
    print(f"Sending push notification to User {user_id}: {title} - {body}")
    
    log = models.AuditLog(action="send_notification", details=f"To User {user_id}: {title}")
    db.add(log)
    db.commit()
    
    return {"success": True, "message": f"تم إرسال الإشعار لـ {len(tokens)} أجهزة"}
