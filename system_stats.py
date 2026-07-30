import psutil
import time
from datetime import datetime
import os

# استخدام وقت إقلاع النظام الحقيقي
BOOT_TIME = psutil.boot_time()

def get_system_stats():
    # interval=None يضمن عدم تجميد السيرفر أثناء قراءة المعالج
    cpu_usage = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    
    # الحصول على مساحة القرص الجذر (C:\ على ويندوز أو / على لينكس)
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    
    uptime_seconds = time.time() - BOOT_TIME
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(hours)}h {int(minutes)}m"
    
    return {
        "cpu_percent": cpu_usage,
        "ram_percent": memory.percent,
        "ram_used_gb": round(memory.used / (1024**3), 2),
        "ram_total_gb": round(memory.total / (1024**3), 2),
        "disk_percent": disk.percent,
        "uptime": uptime_str,
        "timestamp": datetime.now().isoformat()
    }
