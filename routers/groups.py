from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import schemas
import models
from auth import get_current_user

router = APIRouter(prefix="/api/groups", tags=["Groups"])

@router.post("", response_model=schemas.GroupResponse)
def create_group(group: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_group = models.Group(
        name=group.name,
        avatar=group.avatar,
        owner_id=current_user.id
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    member = models.GroupMember(
        group_id=db_group.id,
        user_id=current_user.id,
        is_admin=True
    )
    db.add(member)
    
    epoch = models.GroupEpoch(
        group_id=db_group.id,
        epoch_number=1,
        encryption_state="{}"
    )
    db.add(epoch)
    
    log = models.AuditLog(action="create_group", details=f"تم إنشاء مجموعة {group.name}")
    db.add(log)
    
    db.commit()
    return db_group

@router.get("", response_model=List[schemas.GroupResponse])
def get_user_groups(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    memberships = db.query(models.GroupMember).filter(models.GroupMember.user_id == current_user.id).all()
    group_ids = [m.group_id for m in memberships]
    groups = db.query(models.Group).filter(models.Group.id.in_(group_ids)).all()
    return groups

@router.get("/{group_id}", response_model=schemas.GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
         raise HTTPException(status_code=404, detail="المجموعة غير موجودة")
    return group

@router.put("/{group_id}", response_model=schemas.GroupResponse)
def update_group(group_id: int, group_data: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    member = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id
    ).first()
    
    if not member or not member.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل المجموعة")
        
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    group.name = group_data.name
    group.avatar = group_data.avatar
    db.commit()
    db.refresh(group)
    return group

@router.post("/{group_id}/members")
def add_group_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    admin = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id,
        models.GroupMember.is_admin == True
    ).first()
    if not admin:
        raise HTTPException(status_code=403, detail="غير مصرح بإضافة أعضاء")
        
    existing = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == user_id
    ).first()
    if existing:
         raise HTTPException(status_code=400, detail="المستخدم عضو بالفعل")
         
    new_member = models.GroupMember(group_id=group_id, user_id=user_id)
    db.add(new_member)
    
    # Create new epoch for key rotation
    latest_epoch = db.query(models.GroupEpoch).filter(models.GroupEpoch.group_id == group_id).order_by(models.GroupEpoch.epoch_number.desc()).first()
    new_epoch_num = (latest_epoch.epoch_number + 1) if latest_epoch else 1
    new_epoch = models.GroupEpoch(group_id=group_id, epoch_number=new_epoch_num, encryption_state="{}")
    db.add(new_epoch)
    
    db.commit()
    return {"success": True, "message": "تم إضافة العضو"}

@router.delete("/{group_id}/members/{user_id}")
def remove_group_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    admin = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id,
        models.GroupMember.is_admin == True
    ).first()
    if not admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="غير مصرح بحذف أعضاء")
        
    member = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == user_id
    ).first()
    if not member:
         raise HTTPException(status_code=404, detail="العضو غير موجود")
         
    db.delete(member)
    
    # Create new epoch for key rotation
    latest_epoch = db.query(models.GroupEpoch).filter(models.GroupEpoch.group_id == group_id).order_by(models.GroupEpoch.epoch_number.desc()).first()
    new_epoch_num = (latest_epoch.epoch_number + 1) if latest_epoch else 1
    new_epoch = models.GroupEpoch(group_id=group_id, epoch_number=new_epoch_num, encryption_state="{}")
    db.add(new_epoch)
    
    db.commit()
    return {"success": True}

@router.get("/{group_id}/messages", response_model=List[schemas.MessageResponse])
def get_group_messages(group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    member = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="لست عضواً في هذه المجموعة")
        
    messages = db.query(models.Message).filter(models.Message.group_id == group_id).order_by(models.Message.created_at.asc()).all()
    return messages

@router.post("/{group_id}/messages", response_model=schemas.MessageResponse)
def send_group_message(group_id: int, msg: schemas.MessageBase, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    member = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="لست عضواً في هذه المجموعة")
        
    db_msg = models.Message(
        sender_id=current_user.id,
        group_id=group_id,
        ciphertext=msg.ciphertext,
        type=msg.type,
        file_id=msg.file_id
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    
    from mesibo_api import send_message_via_mesibo
    members = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).all()
    
    for mem in members:
        if mem.user_id != current_user.id:
            user = db.query(models.User).filter(models.User.id == mem.user_id).first()
            if user:
                # Send individual ping via Mesibo to trigger Android BroadcastReceiver
                send_message_via_mesibo(
                    sender_address=current_user.email,
                    receiver_address=user.email,
                    message="[GroupPing]" + msg.ciphertext,
                    group_id=0
                )
    
    return db_msg
