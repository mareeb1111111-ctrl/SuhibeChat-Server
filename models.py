from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database import Base

class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"

class ContactStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="")
    avatar = Column(String, nullable=True)
    address = Column(String, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_logged_in = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_ghost_mode = Column(Boolean, default=False)
    public_key = Column(String, nullable=True)
    
    # Relationships
    messages_sent = relationship("Message", foreign_keys="[Message.sender_id]", back_populates="sender", cascade="all, delete-orphan")
    messages_received = relationship("Message", foreign_keys="[Message.receiver_id]", back_populates="receiver", cascade="all, delete-orphan")
    groups_owned = relationship("Group", back_populates="owner", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", foreign_keys="[Contact.user_id]", back_populates="user", cascade="all, delete-orphan")
    contact_requests_sent = relationship("ContactRequest", foreign_keys="[ContactRequest.sender_id]", back_populates="sender", cascade="all, delete-orphan")
    contact_requests_received = relationship("ContactRequest", foreign_keys="[ContactRequest.receiver_id]", back_populates="receiver", cascade="all, delete-orphan")
    files = relationship("FileRecord", back_populates="uploader", cascade="all, delete-orphan")
    notifications = relationship("NotificationToken", back_populates="user", cascade="all, delete-orphan")

class OTPRequest(Base):
    __tablename__ = "otp_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    otp = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0)
    verified = Column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False) 
    details = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    content = Column(String, nullable=False)
    type = Column(String, default=MessageType.TEXT.value) 
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    is_read = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)
    burn_timer = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    sender = relationship("User", foreign_keys=[sender_id], back_populates="messages_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="messages_received")
    group = relationship("Group", back_populates="messages")
    file = relationship("FileRecord")

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    avatar = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="groups_owned")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = "group_members"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_admin = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")

class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", foreign_keys=[user_id], back_populates="contacts")
    contact = relationship("User", foreign_keys=[contact_id])

class ContactRequest(Base):
    __tablename__ = "contact_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default=ContactStatus.PENDING.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    sender = relationship("User", foreign_keys=[sender_id], back_populates="contact_requests_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="contact_requests_received")

class FileRecord(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    uploader = relationship("User", back_populates="files")

class NotificationToken(Base):
    __tablename__ = "notification_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fcm_token = Column(String, nullable=False, unique=True)
    device_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="notifications")
