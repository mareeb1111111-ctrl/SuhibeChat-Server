#!/bin/bash
set -e

# إنشاء المجلدات إذا لم تكن موجودة (تحوطاً)
mkdir -p /app/uploads /app/logs /tmp

# تنفيذ الأمر الرئيسي الممرر للحاوية
exec "$@"
