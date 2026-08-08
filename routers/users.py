from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
from datetime import datetime, timedelta, timezone

from database import get_db
import schemas
import models
from auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("", response_model=schemas.UserListResponse)
def get_users(search: str = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.User)
    if search:
        query = query.filter(
            (models.User.name.ilike(f"%{search}%")) | (models.User.email.ilike(f"%{search}%"))
        )
    users = query.all()
    return {"users": users, "count": len(users)}

@router.get("/online", response_model=List[schemas.UserResponse])
def get_online_users(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    return db.query(models.User).filter(
        models.User.last_login >= five_mins_ago,
        models.User.is_ghost_mode == False
    ).all()

@router.put("/me/ghost", response_model=schemas.UserResponse)
def toggle_ghost_mode(request: schemas.UserGhostUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    current_user.is_ghost_mode = request.is_ghost_mode
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_profile(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return user

@router.put("/{user_id}", response_model=schemas.UserResponse)
def update_user(user_id: int, update_data: schemas.UserBase, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل بيانات مستخدم آخر")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
         raise HTTPException(status_code=404, detail="المستخدم غير موجود")
         
    user.name = update_data.name
    user.address = update_data.address
    if update_data.avatar:
        user.avatar = update_data.avatar
        
    db.commit()
    db.refresh(user)
    return user

@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    upload_dir = "uploads"
    file_path = os.path.join(upload_dir, f"avatar_{current_user.id}_{datetime.now().timestamp()}.png")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    current_user.avatar = file_path
    db.commit()
    return {"success": True, "avatar": file_path}

@router.post("/public-key")
def update_public_key(request: schemas.PublicKeyRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    current_user.public_key = request.public_key
    db.commit()
    return {"success": True, "message": "Public key updated successfully"}
