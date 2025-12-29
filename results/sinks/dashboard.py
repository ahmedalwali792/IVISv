import cv2
import numpy as np
import sys
import requests  # <--- هذا هو الاستيراد الناقص
from results.sinks.base import BaseSink

class DashboardSink(BaseSink):
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.window_name = "Result Plane"
        try:
            # اختبار سريع لـ GUI
            dummy = np.zeros((10, 10), dtype='uint8')
            cv2.imshow("Test", dummy)
            cv2.destroyWindow("Test")
            self.disabled = False
        except:
            self.disabled = True

    def handle(self, result: dict):
        if self.disabled: return
        try:
            canvas = None
            
            # 1. محاولة جلب الصورة من الذاكرة إذا توفر المفتاح
            if "memory" in result:
                try:
                    mem_key = result["memory"]["key"]
                    # الاتصال بخدمة الذاكرة لجلب الصورة الخام
                    resp = requests.get(f"http://localhost:6000/{mem_key}", timeout=0.1)
                    if resp.status_code == 200:
                        # تحويل البيانات (Bytes) إلى صورة
                        arr = np.frombuffer(resp.content, dtype=np.uint8)
                        canvas = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                except Exception:
                    pass # فشل الجلب، سنكمل بخلفية سوداء

            # 2. إذا لم تنجح عملية الجلب، أنشئ خلفية سوداء
            if canvas is None:
                canvas = np.zeros((self.h, self.w, 3), dtype='uint8')

            # 3. الرسم على الصورة (سواء كانت فيديو حقيقي أو شاشة سوداء)
            fid = result.get("frame_id", "N/A")
            cv2.putText(canvas, f"ID: {fid[:8]}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            for det in result.get("detections", []):
                # رسم المربعات الوهمية
                if "bbox" in det:
                    x, y, w, h = det["bbox"]
                    cv2.rectangle(canvas, (x, y), (x+w, y+h), (0, 255, 255), 2)
            
            # 4. العرض
            cv2.imshow(self.window_name, canvas)
            
            # زر الخروج 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'): sys.exit(0)
            
        except SystemExit:
            sys.exit(0)
        except Exception:
            # أي خطأ آخر لا نوقف الخدمة، فقط نتجاهل الإطار
            pass