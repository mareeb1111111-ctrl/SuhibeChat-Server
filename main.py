
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import asyncio
import json
import os
import re
import logging
import sys
from datetime import datetime, timedelta, timezone

from config import settings
from database import engine, Base, get_db, SessionLocal
from models import User, OTPRequest, AuditLog
import schemas
import auth
import mesibo_api
import system_stats
from smtp import send_otp_email, send_invite_email
from routers import users, messages, groups, contacts, files, notifications, stats

logger = logging.getLogger(__name__)

# إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(bind=engine)

# إعداد السجلات لتظهر فوراً
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

app = FastAPI()

app = FastAPI(title=settings.APP_NAME)


@app.get("/")
def read_root():
    return {"message": "SuhibeChat is running!"}

@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    if not request.url.path.startswith(("/static", "/uploads", "/dashboard")):
        logger.info(f"🌍 INCOMING REQUEST: {request.method} {request.url.path} from {request.client.host}")
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("dashboard", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(users.router)
app.include_router(messages.router)
app.include_router(groups.router)
app.include_router(contacts.router)
app.include_router(files.router)
app.include_router(notifications.router)
app.include_router(stats.router)

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    with open("dashboard/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/dashboard/style.css")
async def get_dashboard_css():
    with open("dashboard/style.css", "r", encoding="utf-8") as f:
        from fastapi.responses import Response
        return Response(content=f.read(), media_type="text/css")

@app.get("/dashboard/app.js")
async def get_dashboard_js():
    with open("dashboard/app.js", "r", encoding="utf-8") as f:
        from fastapi.responses import Response
        return Response(content=f.read(), media_type="application/javascript")


@app.post("/api/request-otp", response_model=dict)
async def request_otp(req: schemas.OTPRequestBase, db: Session = Depends(get_db)):
    try:
        email = str(req.email)
        otp = auth.create_otp_request(db, email)
        
        user = auth.find_user_by_email(db, email)
        name = user.name if user else None
        
        email_sent = await send_otp_email(email, otp, name)
        
        if email_sent:
            return {"success": True, "message": "تم إرسال الرمز إلى بريدك الإلكتروني"}
        else:
            return {"success": True, "message": "تم إنشاء الرمز لكن فشل إرسال البريد. تحقق من إعدادات SMTP."}
    except ValueError as e:
        logger.error(f"OTP Request error for {req.email}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in request-otp for {req.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="حدث خطأ غير متوقع")

@app.post("/api/invite", response_model=dict)
async def invite_user(req: schemas.OTPRequestBase, db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    email = str(req.email)
    existing_user = auth.find_user_by_email(db, email)
    if existing_user:
        raise HTTPException(status_code=400, detail="المستخدم مسجل مسبقاً")
        
    sent = await send_invite_email(email, current_user.name)
    if sent:
        log = AuditLog(action="send_invite", details=f"تم إرسال دعوة إلى {email} بواسطة {current_user.email}")
        db.add(log)
        db.commit()
        return {"success": True, "message": "تم إرسال الدعوة بنجاح"}
    else:
        raise HTTPException(status_code=500, detail="فشل في إرسال الدعوة عبر البريد")

@app.post("/api/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(req: schemas.OTPVerifyRequest, db: Session = Depends(get_db)):
    try:
        email = str(req.email)
        auth.verify_otp_request(db, email, req.otp)
        user = auth.get_or_create_user(db, email)
        
        mesibo_resp = mesibo_api.add_user_to_mesibo(email, user.name, user.address)
        if not mesibo_resp["success"]:
            logger.error(f"Mesibo API Error for {email}: {mesibo_resp.get('error')}")
            raise HTTPException(status_code=500, detail=mesibo_resp.get("error", "Failed to get Mesibo token"))
            
        access_token = auth.create_access_token(data={"sub": user.email})
            
        return {
            "success": True,
            "token": mesibo_resp["token"],
            "access_token": access_token,
            "user": user
        }
    except ValueError as e:
         logger.error(f"Verify OTP Error for {req.email}: {str(e)}")
         raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/logout", response_model=dict)
def logout(db: Session = Depends(get_db), current_user: User = Depends(auth.get_current_user)):
    current_user.is_logged_in = False
    db.commit()
    log = AuditLog(action="logout", details=f"تسجيل خروج المستخدم {current_user.email}")
    db.add(log)
    db.commit()
    return {"success": True, "message": "تم تسجيل الخروج بنجاح"}

@app.post("/api/register", response_model=dict)
async def register(req: schemas.UserRegister, db: Session = Depends(get_db)):
    try:
        email = str(req.email)
        auth.register_user(db, email, req.name)
        
        # إنشاء وإرسال الـ OTP بعد التسجيل بنجاح
        otp = auth.create_otp_request(db, email)
        email_sent = await send_otp_email(email, otp, req.name)
        
        if email_sent:
            return {"success": True, "message": "تم التسجيل بنجاح، تم إرسال رمز التحقق إلى بريدك الإلكتروني"}
        else:
            return {"success": True, "message": "تم التسجيل بنجاح، لكن فشل إرسال البريد. راجع الـ Terminal للحصول على الرمز الاحتياطي."}
    except ValueError as e:
        logger.error(f"Registration Error for {req.email}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected Registration Error for {req.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="حدث خطأ غير متوقع أثناء التسجيل.")

def get_active_users_count(db: Session) -> int:
    five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    return db.query(User).filter(User.last_login >= five_mins_ago).count()

@app.api_route("/mesiboapi", methods=["GET", "POST", "PUT"])
async def mesibo_api_handler(request: Request):
    logger.info("========== MESIBO REQUEST START ==========")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Query Params: {dict(request.query_params)}")
    
    try:
        data = await request.json()
        logger.info(f"JSON Payload: {data}")
    except Exception:
        try:
            form = await request.form()
            if form:
                logger.info(f"Form Payload: {dict(form)}")
            else:
                body = await request.body()
                logger.info(f"Raw Body: {body}")
        except Exception:
            body = await request.body()
            logger.info(f"Raw Body: {body}")
            
    logger.info("========== MESIBO REQUEST END ==========")
    
    # يجب إرجاع {"result": "OK"} للعديد من عمليات Mesibo لكي لا يقوم المحرك بقطع الاتصال
    return {"result": "OK", "op": request.query_params.get("op", "unknown")}

@app.get("/api/system-stats")
def get_api_system_stats():
    return system_stats.get_system_stats()

@app.get("/api/user-stats")
def get_api_user_stats(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    active_users = get_active_users_count(db)
    
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    registered_today = db.query(User).filter(User.created_at >= today).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "registered_today": registered_today
    }

@app.get("/api/call-stats")
def get_api_call_stats(db: Session = Depends(get_db)):
    return {
        "active_calls": 0,
        "audio_calls": 0,
        "video_calls": 0
    }

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/stats")
async def websocket_stats_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def push_stats_to_dashboard():
    system_stats.get_system_stats()
    
    while True:
        await asyncio.sleep(2.5) 
        db = SessionLocal()
        try:
            sys_stats = system_stats.get_system_stats()
            total_users = db.query(User).count()
            active_users = get_active_users_count(db)
            recent_logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(10).all()
            
            messages_ps = 0 
            active_calls = 0

            data = {
                "system": sys_stats,
                "users": {
                    "total": total_users,
                    "active": active_users
                },
                "activity": {
                    "messages_per_sec": messages_ps,
                    "active_calls": active_calls
                },
                "logs": [{"action": log.action, "details": log.details, "time": log.created_at.strftime("%H:%M:%S")} for log in recent_logs]
            }
            
            await manager.broadcast(json.dumps(data))
        except Exception as e:
            logger.error(f"WebSocket Push Error: {e}")
        finally:
            db.close()

@app.on_event("startup")
async def startup_event():
    logger.info("✅ السيرفر يعمل بنجاح ومستعد لاستقبال طلبات Mesibo على المنفذ 5000!")
    asyncio.create_task(push_stats_to_dashboard())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
