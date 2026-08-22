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

@router.get("/unread", response_model=schemas.MessageListResponse)
def get_unread_messages(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    messages = db.query(models.Message).options(joinedload(models.Message.file)).filter(
        models.Message.receiver_id == current_user.id,
        models.Message.is_read == False
    ).order_by(models.Message.created_at.asc()).all()
    return {"messages": messages, "count": len(messages)}

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
def get_messages(user_id: int, after_id: int = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Message).options(joinedload(models.Message.file)).filter(
        or_(
            (models.Message.sender_id == current_user.id) & (models.Message.receiver_id == user_id),
            (models.Message.sender_id == user_id) & (models.Message.receiver_id == current_user.id)
        )
    )
    if after_id is not None:
        query = query.filter(models.Message.id > after_id)
        
    messages = query.order_by(models.Message.created_at.asc()).all()
    return {"messages": messages, "count": len(messages)}

@router.post("", response_model=schemas.MessageResponse)
def send_message(msg: schemas.MessageCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    try:
        is_encrypted = False
        import base64
        prefixes = ["E2EE:", "MSG:", "PREKEY:", "E2EE_GRP:", "GROUP_KEY_REQ:", "SENDERKEY:"]
        
        if msg.type == "public_key" or msg.type == "encrypted":
            is_encrypted = True
        else:
            for p in prefixes:
                if msg.ciphertext.startswith(p):
                    b64_part = msg.ciphertext[len(p):]
                    try:
                        decoded = base64.b64decode(b64_part, validate=True)
                        # Signal protocol version 3 ciphertexts usually start with 0x33 or similar.
                        # However, to maintain server blindness strictly without risking false positives,
                        # we ensure the base64 is cryptographically valid and non-empty.
                        if len(decoded) > 0:
                            is_encrypted = True
                            break
                    except Exception:
                        pass
                        
        if not is_encrypted:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message rejected: Invalid E2EE format or plaintext detected")
            
        if msg.client_message_id:
            existing_msg = db.query(models.Message).filter(
                models.Message.client_message_id == msg.client_message_id,
                models.Message.sender_id == current_user.id
            ).first()
            if existing_msg:
                logger.info(f"Duplicate message detected: client_message_id={msg.client_message_id}")
                return db.query(models.Message).options(joinedload(models.Message.file)).filter(models.Message.id == existing_msg.id).first()
            
        db_msg = models.Message(
            client_message_id=msg.client_message_id,
            sender_id=current_user.id,
            receiver_id=msg.receiver_id,
            group_id=msg.group_id,
            ciphertext=msg.ciphertext,
            type=msg.type,
            file_id=msg.file_id,
            is_encrypted=is_encrypted,
            burn_timer=msg.burn_timer
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)
        
        receiver_email = ""
        receiver_user = db.query(models.User).filter(models.User.id == msg.receiver_id).first()
        if receiver_user:
            receiver_email = receiver_user.email
                
        mesibo_api.send_message_via_mesibo(
            sender_address=current_user.email,
            receiver_address=receiver_email,
            message=msg.ciphertext,
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
        if not (msg.receiver_id == current_user.id and msg.burn_timer != None and msg.burn_timer > 0):
            logger.warning(f"Delete failed: User {current_user.id} unauthorized to delete message {message_id} sent by {msg.sender_id}")
            raise HTTPException(status_code=403, detail="لا يمكنك حذف هذه الرسالة")
        
    db.delete(msg)
    db.commit()
    logger.info(f"Message {message_id} deleted successfully by user {current_user.id}")
    return {"success": True}
