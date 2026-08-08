from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from database import get_db
import schemas
import models
from auth import get_current_user
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging
import mesibo_api

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/messages", tags=["Messages"])

@router.get("/chats")
def get_chats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    sent_msgs = db.query(models.Message.receiver_id).filter(models.Message.sender_id == current_user.id).all()
    received_msgs = db.query(models.Message.sender_id).filter(models.Message.receiver_id == current_user.id).all()
    
    partner_ids = set([msg[0] for msg in sent_msgs] + [msg[0] for msg in received_msgs])
    
    if not partner_ids:
        return {"users": [], "count": 0}
        
    users = db.query(models.User).filter(models.User.id.in_(partner_ids)).all()
    return {"users": users, "count": len(users)}

@router.get("/{user_id}", response_model=schemas.MessageListResponse)
def get_messages(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    messages = db.query(models.Message).options(joinedload(models.Message.file)).filter(
        or_(
            (models.Message.sender_id == current_user.id) & (models.Message.receiver_id == user_id),
            (models.Message.sender_id == user_id) & (models.Message.receiver_id == current_user.id)
        )
    ).order_by(models.Message.created_at.asc()).all()
    return {"messages": messages, "count": len(messages)}

@router.post("", response_model=schemas.MessageResponse)
def send_message(msg: schemas.MessageCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    try:
        logger.info(f"Received message payload from {current_user.email}: {msg.dict()}")
        
        is_encrypted = False
        if msg.content.startswith("E2EE:") or msg.type == "public_key" or msg.type == "encrypted":
            is_encrypted = True
            
        db_msg = models.Message(
            sender_id=current_user.id,
            receiver_id=msg.receiver_id,
            group_id=msg.group_id,
            content=msg.content,
            type=msg.type,
            file_id=msg.file_id,
            is_encrypted=is_encrypted
        )
        db.add(db_msg)
        
        if not is_encrypted:
            log = models.AuditLog(action="send_message", details=f"رسالة من {current_user.email}")
            db.add(log)
        
        db.commit()
        db.refresh(db_msg)
        
        receiver_email = ""
        receiver_user = db.query(models.User).filter(models.User.id == msg.receiver_id).first()
        if receiver_user:
            receiver_email = receiver_user.email
                
        mesibo_api.send_message_via_mesibo(
            sender_address=current_user.email,
            receiver_address=receiver_email,
            message=msg.content,
            group_id=msg.group_id or 0
        )
        
        # Reload with file relation to ensure it is returned in the response
        db_msg_reloaded = db.query(models.Message).options(joinedload(models.Message.file)).filter(models.Message.id == db_msg.id).first()
        return db_msg_reloaded
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{message_id}/read")
def mark_message_as_read(message_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    msg = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
    if msg.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذه الرسالة")
        
    if not current_user.is_ghost_mode:
        msg.is_read = True
        db.commit()
    return {"success": True}

@router.delete("/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    msg = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not msg:
        logger.warning(f"Delete failed: Message {message_id} not found. Requested by user {current_user.id}")
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
    if msg.sender_id != current_user.id:
        logger.warning(f"Delete failed: User {current_user.id} unauthorized to delete message {message_id} sent by {msg.sender_id}")
        raise HTTPException(status_code=403, detail="لا يمكنك حذف هذه الرسالة")
        
    db.delete(msg)
    db.commit()
    logger.info(f"Message {message_id} deleted successfully by user {current_user.id}")
    return {"success": True}
