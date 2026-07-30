import logging
import random
import string
import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from models import OTPRequest, User, AuditLog
from database import get_db
from config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/verify-otp")

def generate_otp() -> str:
    return ''.join(random.choices(string.digits, k=6))

def find_user_by_email(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).first()

def register_user(db: Session, email: str, name: str) -> User:
    existing_user = find_user_by_email(db, email)
    if existing_user:
        logger.error(f"Registration failed: User {email} already exists.")
        raise ValueError("البريد الإلكتروني مسجل مسبقاً.")
        
    user = User(email=email, name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    log = AuditLog(action="create_user", details=f"تم تسجيل المستخدم {email} عبر API")
    db.add(log)
    db.commit()
    return user

def create_otp_request(db: Session, email: str) -> str:
    now = datetime.now(timezone.utc)
    
    recent_attempts = db.query(OTPRequest).filter(
        OTPRequest.email == email,
        OTPRequest.created_at > now - timedelta(seconds=settings.OTP_BLOCK_DURATION),
        OTPRequest.attempts >= settings.OTP_MAX_ATTEMPTS
    ).first()
    
    if recent_attempts:
        logger.error(f"OTP Request failed for {email}: Blocked due to too many attempts.")
        raise ValueError(f"تم حظر هذا البريد لمدة {settings.OTP_BLOCK_DURATION // 60} دقائق بسبب كثرة المحاولات.")
        
    # التحقق من وجود OTP غير منتهي وغير مستخدم
    existing_valid_otp = db.query(OTPRequest).filter(
        OTPRequest.email == email,
        OTPRequest.expires_at > now,
        OTPRequest.verified == False
    ).first()
    
    if existing_valid_otp:
        logger.warning(f"OTP Request rejected for {email}: Valid OTP already exists.")
        raise ValueError("رمز التحقق صالح بالفعل، يرجى التحقق من بريدك الإلكتروني")
        
    otp = generate_otp()
    expires_at = now + timedelta(seconds=settings.OTP_EXPIRY)
    
    db_otp = OTPRequest(email=email, otp=otp, expires_at=expires_at)
    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)
    
    logger.info(f"Generated new OTP for {email}")
    print(f"\n---> MOCK/FALLBACK: OTP for {email} is {otp} <---\n")
    return otp

def verify_otp_request(db: Session, email: str, otp: str) -> bool:
    now = datetime.now(timezone.utc)
    logger.info(f"Verifying OTP for email: {email}. Received OTP: {otp}")
    
    req = db.query(OTPRequest).filter(
        OTPRequest.email == email,
        OTPRequest.verified == False
    ).order_by(OTPRequest.created_at.desc()).first()
    
    if not req:
        logger.error(f"OTP verification failed for {email}: No pending OTP request found.")
        raise ValueError("لم يتم العثور على طلب رمز تحقق.")
        
    logger.info(f"Found OTP request in DB. DB OTP: {req.otp}. Expires at: {req.expires_at}")
        
    expires_at = req.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at < now:
        logger.error(f"OTP verification failed for {email}: OTP expired.")
        raise ValueError("انتهت صلاحية الرمز، يرجى طلب رمز جديد.")
        
    if req.attempts >= settings.OTP_MAX_ATTEMPTS:
        logger.error(f"OTP verification failed for {email}: Max attempts reached.")
        raise ValueError("تم تجاوز الحد الأقصى للمحاولات.")
        
    if req.otp != otp:
        req.attempts += 1
        db.commit()
        attempts_left = settings.OTP_MAX_ATTEMPTS - req.attempts
        logger.warning(f"OTP verification failed for {email}: Invalid OTP. Attempts left: {attempts_left}")
        raise ValueError(f"الرمز غير صحيح، عدد المحاولات المتبقية: {attempts_left}")
        
    req.verified = True
    db.commit()
    logger.info(f"OTP verified successfully for {email}")
    return True

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    # تحويل Byte إلى String في حال كان PyJWT بنسخة قديمة (رغم أن النسخ الحديثة تعيد String مباشرة)
    if isinstance(encoded_jwt, bytes):
        encoded_jwt = encoded_jwt.decode("utf-8")
        
    logger.info(f"Generated JWT Token: {encoded_jwt}")
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    logger.info(f"Received Token for Auth: '{token}'")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        logger.error("Authentication failed: No token provided.")
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            logger.error("Authentication failed: Token payload missing 'sub' (email).")
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        logger.error("Authentication failed: Token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger.error(f"Authentication failed: JWT Decode Error - {str(e)}")
        raise credentials_exception
        
    user = find_user_by_email(db, email=email)
    if user is None:
        logger.error(f"Authentication failed: User with email {email} not found in DB.")
        raise credentials_exception
        
    if not user.is_active:
        logger.error(f"Authentication failed: User {email} is inactive.")
        raise credentials_exception
        
    return user
    
def get_or_create_user(db: Session, email: str, name: str = "", address: str = "") -> User:
    user = find_user_by_email(db, email)
    if not user:
        user = User(email=email, name=name, address=address, is_logged_in=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        log = AuditLog(action="create_user", details=f"تم إنشاء المستخدم {email} تلقائياً بعد التحقق")
        db.add(log)
        db.commit()
    else:
        if user.is_logged_in:
            logger.warning(f"Concurrent login detected for {email}")
            # Optional: You could raise an error here if you strictly want to prevent it,
            # but usually we just log or overwrite the session. Let's strictly prevent it:
            # raise ValueError("هذا الحساب مسجل الدخول حالياً من جهاز آخر.")
            
        user.last_login = datetime.now(timezone.utc)
        user.is_logged_in = True
        db.commit()
        
        log = AuditLog(action="login", details=f"تسجيل دخول المستخدم {email}")
        db.add(log)
        db.commit()
        
    return user
