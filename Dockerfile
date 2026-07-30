# استخدام صورة بايثون خفيفة
FROM python:3.10-slim

# منع بايثون من إنشاء ملفات .pyc وتفعيل طباعة السجلات مباشرة
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# إنشاء مستخدم غير جذري (non-root) للأمان
RUN addgroup --system appgroup && adduser --system --group appuser

# تحديث النظام وتثبيت المتطلبات الأساسية
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# تحديد مسار العمل
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# إنشاء المجلدات المطلوبة للتهيئة
RUN mkdir -p /app/uploads /app/logs /tmp

# نسخ سكريبت التهيئة
COPY docker-entrypoint.sh /app/
# تحويل نهايات الأسطر إلى نمط Unix لتجنب مشاكل الويندوز وإعطاء صلاحية التنفيذ
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

# نسخ باقي ملفات المشروع
COPY . /app/

# إعادة تعيين الصلاحيات بعد النسخ
RUN chown -R appuser:appgroup /app /tmp

# التبديل إلى المستخدم غير الجذري
USER appuser

# المنفذ الذي سيعمل عليه التطبيق
EXPOSE 5000

# تشغيل سكريبت التهيئة ثم التطبيق
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
