import aiosmtplib
from email.message import EmailMessage
from config import settings
import logging

logger = logging.getLogger(__name__)

async def send_otp_email(email: str, otp: str, name: str = None):
    subject = "رمز التحقق لتطبيق SuhibeChat"
    greeting = f"مرحباً {name}," if name else "مرحباً،"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; text-align: right; direction: rtl; padding: 20px;">
        <h2 style="color: #3b82f6;">SuhibeChat</h2>
        <p>{greeting}</p>
        <p>رمز التحقق الخاص بك هو:</p>
        <div style="font-size: 24px; font-weight: bold; padding: 10px; background-color: #f3f4f6; border-radius: 5px; display: inline-block; letter-spacing: 2px;">
            {otp}
        </div>
        <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">هذا الرمز صالح لمدة 5 دقائق فقط.</p>
    </div>
    """
    
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = subject
    message.set_content(f"{greeting}\nرمز التحقق الخاص بك هو: {otp}\nصالح لمدة 5 دقائق.")
    message.add_alternative(html_content, subtype='html')
    
    try:
        # إذا كان المنفذ 587 فنحن غالباً نستخدم starttls
        use_tls = settings.SMTP_PORT == 465 or settings.SMTP_USE_TLS
        start_tls = settings.SMTP_PORT == 587
        
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=use_tls,
            start_tls=start_tls,
        )
        print(f"✅ تم إرسال البريد الإلكتروني بنجاح إلى: {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {e}")
        print(f"❌ فشل في إرسال البريد الإلكتروني إلى {email}: {e}")
        return False

async def send_invite_email(email: str, inviter_name: str = None):
    subject = "دعوة للانضمام إلى تطبيق SuhibeChat"
    inviter = inviter_name if inviter_name else "أحد أصدقائك"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; text-align: right; direction: rtl; padding: 20px;">
        <h2 style="color: #3b82f6;">SuhibeChat</h2>
        <p>مرحباً،</p>
        <p>لقد قام <b>{inviter}</b> بدعوتك للانضمام إلى تطبيق المحادثة SuhibeChat.</p>
        <p>تطبيقنا يوفر بيئة آمنة وسريعة للتواصل المباشر والمجموعات!</p>
        <a href="https://example.com/download" style="display: inline-block; padding: 10px 20px; background-color: #3b82f6; color: white; text-decoration: none; border-radius: 5px; margin-top: 15px;">تحميل التطبيق الآن</a>
    </div>
    """
    
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = subject
    message.set_content(f"لقد قام {inviter} بدعوتك لتحميل التطبيق. قم بزيارة: https://example.com/download")
    message.add_alternative(html_content, subtype='html')
    
    try:
        use_tls = settings.SMTP_PORT == 465 or settings.SMTP_USE_TLS
        start_tls = settings.SMTP_PORT == 587
        
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=use_tls,
            start_tls=start_tls,
        )
        print(f"✅ تم إرسال دعوة بنجاح إلى: {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send invite email to {email}: {e}")
        print(f"❌ فشل في إرسال بريد الدعوة إلى {email}: {e}")
        return False
