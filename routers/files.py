from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import shutil
import os
from datetime import datetime

from database import get_db
import schemas
import models
from auth import get_current_user

router = APIRouter(prefix="/api/files", tags=["Files"])
UPLOAD_DIR = "uploads"

@router.post("/upload", response_model=schemas.FileRecordResponse)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    file_path = os.path.join(UPLOAD_DIR, f"{datetime.now().timestamp()}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(file_path)
    if file_size > 20 * 1024 * 1024:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح (20 ميغابايت)")
    
    db_file = models.FileRecord(
        uploader_id=current_user.id,
        file_path=file_path,
        file_type=file.content_type,
        size=file_size
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

@router.delete("/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    file = db.query(models.FileRecord).filter(models.FileRecord.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="الملف غير موجود")
        
    if file.uploader_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="غير مصرح بحذف هذا الملف")
        
    if os.path.exists(file.file_path):
        os.remove(file.file_path)
        
    db.delete(file)
    db.commit()
    return {"success": True, "message": "تم حذف الملف بنجاح"}
