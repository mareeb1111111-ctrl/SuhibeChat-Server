import requests
from config import settings
import logging

logger = logging.getLogger(__name__)

def add_user_to_mesibo(email: str, name: str = "", address: str = "") -> dict:
    """
    Calls Mesibo Backend API to create a user and get an access token.
    """
    # تخطي الاتصال بـ Mesibo إذا لم يتم إعداد التوكن الحقيقي
    if settings.APP_TOKEN == "your_mesibo_app_token_here":
        logger.warning(f"⚠️ تحذير: لم يتم إعداد APP_TOKEN لـ Mesibo. سيتم إرجاع توكن وهمي للمستخدم {email}.")
        return {"success": True, "token": "mock_mesibo_token_for_testing_only"}

    payload = {
        "op": "useradd",
        "token": settings.APP_TOKEN,
        "user": {
            "address": email,
            "token": {
                "appid": "com.example.suhibechat", # Can be modified later
                "expiry": 525600 # 1 year in minutes
            },
            "name": name if name else email
        }
    }
    
    try:
        response = requests.post(settings.MESIBO_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("result") == "OK" or data.get("result") == True or "user" in data:
             user_token = data.get("user", {}).get("token")
             if not user_token:
                 user_token = data.get("token") # fallback
             return {"success": True, "token": user_token}
        else:
             logger.error(f"Mesibo API Error: {data}")
             return {"success": False, "error": data.get("error", "Unknown error")}
    except Exception as e:
        logger.error(f"Failed to connect to Mesibo API: {str(e)}")
        return {"success": False, "error": str(e)}

def send_message_via_mesibo(sender_address: str, receiver_address: str, message: str, group_id: int = 0) -> bool:
    """
    يرسل رسالة مباشرة عبر واجهة برمجة Mesibo Backend ليتم تسليمها بالوقت الفعلي
    """
    if settings.APP_TOKEN == "your_mesibo_app_token_here":
        return True

    payload = {
        "op": "message",
        "token": settings.APP_TOKEN,
        "message": {
            "from": sender_address,
            "type": 1,
            "message": message
        }
    }
    
    if group_id:
        payload["message"]["groupid"] = group_id
    else:
        payload["message"]["to"] = receiver_address
        
    try:
        response = requests.post(settings.MESIBO_API_URL, json=payload, timeout=5)
        data = response.json()
        if data.get("result") == "OK" or data.get("result") == True:
            logger.info(f"Message sent to Mesibo Real-time engine successfully: {sender_address} -> {receiver_address or group_id}")
            return True
        else:
            logger.error(f"Mesibo Backend Msg Error: {data}")
            return False
    except Exception as e:
        logger.error(f"Failed to send msg to Mesibo Backend: {e}")
        return False
