from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timedelta, timezone

from database import get_db
from models import User, Status, StatusView, Contact
import schemas
from auth import get_current_user

router = APIRouter(
    prefix="/api/statuses",
    tags=["statuses"]
)

@router.post("", response_model=schemas.StatusResponse)
def create_status(
    status_in: schemas.StatusCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    
    if status_in.duration_type == "FIXED_DURATION" and status_in.duration_value:
        try:
            hours = int(status_in.duration_value)
            expires_at = now + timedelta(hours=hours)
        except ValueError:
            expires_at = now + timedelta(hours=24)
    else:
        expires_at = now + timedelta(hours=24) # Default fallback
    
    new_status = Status(
        user_id=current_user.id,
        parent_id=status_in.parent_id,
        moment_type=status_in.moment_type,
        audience=status_in.audience,
        duration_type=status_in.duration_type,
        duration_value=status_in.duration_value,
        type=status_in.type,
        content=status_in.content,
        encryption_key=status_in.encryption_key,
        is_anonymous=status_in.is_anonymous,
        allow_screenshot=status_in.allow_screenshot,
        expires_at=expires_at
    )
    
    db.add(new_status)
    db.commit()
    db.refresh(new_status)
    
    return new_status

@router.get("/feed", response_model=schemas.StatusFeedResponse)
def get_status_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    
    # 1. My active root statuses
    my_statuses = db.query(Status).options(joinedload(Status.updates)).filter(
        Status.user_id == current_user.id,
        Status.expires_at > now,
        Status.parent_id.is_(None)
    ).order_by(Status.created_at.desc()).all()
    
    # 2. Contacts active root statuses
    # Get all my contacts
    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
    contact_ids = [c.contact_id for c in contacts]
    
    if contact_ids:
        contacts_statuses = db.query(Status).options(joinedload(Status.updates)).filter(
            Status.user_id.in_(contact_ids),
            Status.expires_at > now,
            Status.parent_id.is_(None)
        ).order_by(Status.created_at.desc()).all()
    else:
        contacts_statuses = []
        
    return schemas.StatusFeedResponse(
        my_statuses=my_statuses,
        contacts_statuses=contacts_statuses
    )

@router.post("/{status_id}/view")
def view_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if status exists
    status_obj = db.query(Status).filter(Status.id == status_id).first()
    if not status_obj:
        raise HTTPException(status_code=404, detail="Status not found")
        
    # Check if already viewed
    existing_view = db.query(StatusView).filter(
        StatusView.status_id == status_id,
        StatusView.user_id == current_user.id
    ).first()
    
    if not existing_view:
        new_view = StatusView(
            status_id=status_id,
            user_id=current_user.id
        )
        db.add(new_view)
        db.commit()
        
    return {"success": True, "message": "View recorded"}

@router.get("/{status_id}", response_model=schemas.StatusResponse)
def get_status_by_id(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    status_obj = db.query(Status).options(joinedload(Status.updates)).filter(
        Status.id == status_id
    ).first()
    
    if not status_obj:
        raise HTTPException(status_code=404, detail="Status not found")
        
    return status_obj
