from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import schemas
import models
from auth import get_current_user

router = APIRouter(prefix="/api/keys", tags=["Keys"])

@router.post("/upload", response_model=schemas.DeviceKeysResponse)
def upload_keys(keys_data: schemas.DeviceKeysUpload, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check if device already exists globally (since device_id is unique)
    device = db.query(models.Device).filter(
        models.Device.device_id == keys_data.device_id
    ).first()
    
    if device:
        # Update existing keys and reassign to current user if changed
        device.user_id = current_user.id
        device.identity_public_key = keys_data.identity_public_key
        device.signed_pre_key = keys_data.signed_pre_key
        device.one_time_pre_keys = keys_data.one_time_pre_keys
    else:
        # Create new device entry
        device = models.Device(
            user_id=current_user.id,
            device_id=keys_data.device_id,
            identity_public_key=keys_data.identity_public_key,
            signed_pre_key=keys_data.signed_pre_key,
            one_time_pre_keys=keys_data.one_time_pre_keys
        )
        db.add(device)
        
    db.commit()
    db.refresh(device)
    return device

@router.get("/{user_id}", response_model=List[schemas.DeviceKeysResponse])
def get_user_keys(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    devices = db.query(models.Device).filter(models.Device.user_id == user_id).all()
    if not devices:
        raise HTTPException(status_code=404, detail="No devices found for this user")
    return devices
