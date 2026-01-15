# IVISv - Local Developer Notes (عربي)

هدف هذا الدليل: خطوات سريعة لتجهيز المشروع وتشغيله محليًا.

المتطلبات الأساسية
- Python 3.8+ (موصى به 3.10+)
- مساحة تخزين للنموذج (يوجد ملف `yolo11n.pt` في جذر المشروع)

إعداد بيئة افتراضية وتثبيت الاعتمادات (Windows `cmd.exe`):
```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

النماذج
- السكربت `run_system.py` يتوقع `models/yolo.pt` كمسار افتراضي.
- إذا لم يكن ذلك موجودًا، فسينظر تلقائيًا إلى الملف `yolo11n.pt` الموجود في جذر المشروع ويستخدمه كبديل.

تشغيل النظام محليًا (مكون من عدة خدمات):
```bat
python run_system.py
```

تشغيل الخدمات بشكل منفصل بعد التثبيت:
```bat
python -m ingestion.main
python -m detection.main
python -m ui.live_view
```

السجلات
- جميع مخارج الخدمات تُكتب إلى مجلد `logs/` (موجود أو يُنشأ تلقائيًا).
- لا تقم بعمل commit لملفات المخرجات المترجمة مثل `__pycache__/` و`*.pyc` وملفات السجل.

ملاحظات مهمة لتطوير الأداء والاحترافية
- أنشئ بيئة اختبار/CI لتشغيل flake8 وmypy وunit tests.
- النظر في استبدال `infrastructure/bus.py` بوسيلة IPC أكثر متانة (ZeroMQ أو gRPC) للبيئات الإنتاجية.
- على Windows، `signal.SIGALRM` غير متوفّر — الكود يتجاوز مهلات الإرسال تلقائيًا على الأنظمة غير الداعمة.

خطوات مقترحة تالية (يمكنني تنفيذها لك):
- إنشاء ملف `requirements-dev.txt` مع `flake8`, `mypy`, `pytest`.
- إضافة اختبار بسيط يغطي تدفق `memory` PUT/GET.
- تحسين إدارة التكوين (استبدال `sys.path.append` باستعمال حزم مُهيكلة أو استخدام pip install -e .).
