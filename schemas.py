from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class OTPRequestBase(BaseModel):
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class UserRegister(BaseModel):
    email: EmailStr
    name: str
    
class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = ""
    address: Optional[str] = ""
    avatar: Optional[str] = None
    public_key: Optional[str] = None
    is_ghost_mode: Optional[bool] = False

class UserGhostUpdate(BaseModel):
    is_ghost_mode: bool

class PublicKeyRequest(BaseModel):
    public_key: str

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    registered_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    success: bool
    token: str
    access_token: str
    user: UserResponse

class UserListResponse(BaseModel):
    users: List[UserResponse]
    count: int

class MessageBase(BaseModel):
    ciphertext: Optional[str] = ""
    message: Optional[str] = ""
    type: str = "text"
    file_id: Optional[int] = None
    is_encrypted: Optional[bool] = False
    burn_timer: Optional[int] = 0

class MessageCreate(BaseModel):
    receiver_id: int
    ciphertext: str
    type: Optional[str] = "text"
    file_id: Optional[int] = None
    group_id: Optional[int] = None
    burn_timer: Optional[int] = 0

class MessageResponse(MessageBase):
    id: int
    sender_id: int
    receiver_id: Optional[int]
    group_id: Optional[int]
    is_read: bool
    created_at: datetime
    is_encrypted: Optional[bool] = False
    file: Optional['FileRecordResponse'] = None

    class Config:
        from_attributes = True

class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    count: int

class GroupBase(BaseModel):
    name: str
    avatar: Optional[str] = None

class GroupCreate(GroupBase):
    pass

class GroupResponse(GroupBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ContactRequestBase(BaseModel):
    receiver_id: int

class ContactRequestResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class FileRecordResponse(BaseModel):
    id: int
    uploader_id: int
    file_path: str
    file_type: str
    size: int
    uploaded_at: datetime

    class Config:
        from_attributes = True

class NotificationRegister(BaseModel):
    fcm_token: str
    device_type: Optional[str] = None

class DeviceKeysUpload(BaseModel):
    device_id: str
    identity_public_key: str
    signed_pre_key: str
    one_time_pre_keys: Optional[str] = None

class DeviceKeysResponse(DeviceKeysUpload):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

MessageResponse.model_rebuild()
