#!/bin/sh
set -e

# إنشاء المجلدات إذا لم تكن موجودة
mkdir -p /app/uploads /app/logs /tmp

# التحقق من وجود متغيرات البيئة الأساسية (اختياري)
if [ -z "$SECRET_KEY" ]; then
    echo "⚠️ Warning: SECRET_KEY is not set!"
fi

# تنفيذ الأمر الممرر
exec "$@"