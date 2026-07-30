from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from database import get_db
import schemas
import models
from auth import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["Contacts"])

@router.post("/requests", response_model=schemas.ContactRequestResponse)
def send_contact_request(req: schemas.ContactRequestBase, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if req.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="لا يمكنك إرسال طلب لنفسك")
        
    existing = db.query(models.ContactRequest).filter(
        models.ContactRequest.sender_id == current_user.id,
        models.ContactRequest.receiver_id == req.receiver_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="تم إرسال طلب مسبقاً")
        
    db_req = models.ContactRequest(sender_id=current_user.id, receiver_id=req.receiver_id)
    db.add(db_req)
    db.commit()
    db.refresh(db_req)
    return db_req

@router.get("/requests", response_model=dict)
def get_contact_requests(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    incoming = db.query(models.ContactRequest).filter(
        models.ContactRequest.receiver_id == current_user.id,
        models.ContactRequest.status == models.ContactStatus.PENDING.value
    ).all()
    outgoing = db.query(models.ContactRequest).filter(
        models.ContactRequest.sender_id == current_user.id,
        models.ContactRequest.status == models.ContactStatus.PENDING.value
    ).all()
    
    return {
        "incoming": incoming,
        "outgoing": outgoing
    }

@router.put("/requests/{request_id}")
def handle_contact_request(request_id: int, accept: bool, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    req = db.query(models.ContactRequest).filter(models.ContactRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
        
    if req.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="غير مصرح بمعالجة هذا الطلب")
        
    if accept:
        req.status = models.ContactStatus.ACCEPTED.value
        # Add to contacts for both
        c1 = models.Contact(user_id=current_user.id, contact_id=req.sender_id)
        c2 = models.Contact(user_id=req.sender_id, contact_id=current_user.id)
        db.add(c1)
        db.add(c2)
    else:
        req.status = models.ContactStatus.REJECTED.value
        
    db.commit()
    return {"success": True, "status": req.status}

@router.get("", response_model=List[schemas.UserResponse])
def get_contacts(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    contacts = db.query(models.Contact).filter(models.Contact.user_id == current_user.id).all()
    contact_ids = [c.contact_id for c in contacts]
    users = db.query(models.User).filter(models.User.id.in_(contact_ids)).all()
    return users
