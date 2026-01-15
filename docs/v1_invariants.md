V1 Invariants (Frozen)

1. Frame Format invariant

V1 يدعم Frame واحد فقط بهذه المواصفات الحصرية:

Color Space: BGR (OpenCV native)

Data Type: uint8

Layout: Packed (H × W × 3)

❌ غير مدعوم في V1:

Grayscale

Float types

Planar layout

Multi-plane

2. Failure Policy

أي اختلاف في المواصفات أعلاه = Non-Fatal Drop داخل خدمة Detection.

لا محاولة للتحويل أو الإصلاح.

3. Versioning

تغيير هذا السلوك يتطلب الانتقال إلى V2 وتغيير العقد بالكامل.

Notes

The frame contract includes explicit metadata:
- frame_color_space: bgr
- frame_dtype: uint8
- frame_channels: 3

Non-Contractual Components

The following components are explicitly excluded from v1 invariants:

DEV message Bus

Local process orchestration scripts

Changes to these do not constitute a v1 violation.
