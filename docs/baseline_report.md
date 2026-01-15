# تقرير الأساس (Baseline Report)

خلاصة سريعة:

- موقع المشروع: المشروع في جذر المستودع (ملفات مثل `run_system.py`).
- لم تُجرَ أي تغييرات سلوكية على النظام.

1) كيفية التشغيل الحالية

- لتشغيل النظام (مُنسّق):

```
python run_system.py [--source SOURCE] [--source-type auto|file|webcam|rtsp] [--config CONFIG]
[--bus zmq|tcp] [--loop|--no-loop]
```

- ما يفعله `run_system.py` عند التشغيل:
  - يبدأ ثلاث خدمات فرعية باستخدام نفس مفسّر بايثون:
    - `python ingestion/main.py`
    - `python detection/main.py`
    - `python ui/live_view.py`
  - السجلات تُكتب إلى مجلد `logs/` (يُنشأ تلقائياً).
  - الواجهة متوقعة على: http://127.0.0.1:8080

2) المتغيرات البيئية المستخدمة (مقتطف من `run_system.py`)

- إعدادات عامة:
  - `PYTHONPATH`

- متغيرات `ingestion` (مستخدمة عند بدء خدمة الاستيعاب):
  - `MEMORY_BACKEND`, `SHM_BUFFER_BYTES`, `SHM_OWNER`, `RTSP_URL`, `STREAM_ID`, `CAMERA_ID`,
    `TARGET_FPS`, `BUS_TRANSPORT`, `ZMQ_PUB_ENDPOINT`, `ZMQ_RESULTS_SUB_ENDPOINT`,
    `SHM_CACHE_SECONDS`, `SHM_CACHE_FPS`, `FRAME_WIDTH`, `FRAME_HEIGHT`, `FRAME_COLOR`,
    `SELECTOR_MODE`, `ADAPTIVE_FPS`, `ADAPTIVE_MIN_FPS`, `ADAPTIVE_MAX_FPS`,
    `ADAPTIVE_SAFETY`, `VIDEO_LOOP`, `SHM_NAME`, `SHM_META_NAME`

- متغيرات `detection` (مستخدمة عند بدء خدمة الكشف):
  - `MODEL_NAME`, `MODEL_VERSION`, `MODEL_HASH`, `MODEL_PATH`, `INFERENCE_TIMEOUT`, `DEBUG`,
    `MODEL_DEVICE`, `MODEL_HALF`, `MODEL_IMG_SIZE`, `MODEL_CONF`, `MODEL_IOU`,
    `REID_MODEL_PATH`, `REID_ALLOW_FALLBACK`, `BUS_TRANSPORT`, `ZMQ_SUB_ENDPOINT`,
    `ZMQ_RESULTS_PUB_ENDPOINT`, `MEMORY_BACKEND`, `SHM_OWNER`, `SHM_NAME`, `SHM_META_NAME`,
    `SHM_BUFFER_BYTES`, `SHM_CACHE_SECONDS`, `SHM_CACHE_FPS`, `FRAME_WIDTH`, `FRAME_HEIGHT`,
    `KMP_DUPLICATE_LIB_OK`, `FRAME_COLOR`, `MAX_FRAME_AGE_MS`, `TORCH_NUM_THREADS`,
    `TORCH_NUM_INTEROP_THREADS`

- متغيرات `ui` (مستخدمة عند بدء واجهة العرض):
  - `DEBUG`, `ZMQ_SUB_ENDPOINT`, `ZMQ_RESULTS_SUB_ENDPOINT`, `SHM_OWNER`, `STREAM_ID`,
    `CAMERA_ID`, `SHM_NAME`, `SHM_META_NAME`, `SHM_BUFFER_BYTES`, `SHM_CACHE_SECONDS`,
    `SHM_CACHE_FPS`, `FRAME_WIDTH`, `FRAME_HEIGHT`, `FRAME_COLOR`

ملاحظة: يمكن أن تُطبَّق قيم إضافية من ملف التكوين (`--config`) عبر مفتاح `env` أو عبر أقسام `ingestion`/`detection`/`ui`.

3) نتائج التشغيل والاختبارات (سجل)

- pytest:

```
2 passed in 0.48s
```

- تشغيلٍ تجريبي سريع لـ `run_system.py --help`:

```
تمّت طباعة واجهة الاستخدام بنجاح (usage/help) وسطر تسجيل يوضح المفسّر المستخدم.
```

- ملاحظات عن الأخطاء/التحذيرات:
  - لم تُسجّل أخطاء تشغيل أثناء تنفيذ الاختبارات أو عند طلب `--help`.
  - هناك تحذيرات/مسارات محتملة في الكود تشير إلى أن وزنات النماذج قد تكون مفقودة أثناء التشغيل الكامل
    (مثلاً: تحذير عند عدم وجود ملفات النماذج مثل `models/yolo.pt` أو ملفات ReID). هذه التحذيرات
    تظهر فقط عند بدء الخدمات الفعلية (لم تُشغَّل هنا).

4) معلومات بيئة التشغيل

- Python (المفسّر المستخدم للتشغيل التجريبي):

```
Python 3.11.14
```

- `pip freeze` (قائمة الحزم المثبتة):

```
absl-py==2.3.1
annotated-types==0.7.0
antlr4-python3-runtime==4.9.3
anyio==4.11.0
argon2-cffi==25.1.0
argon2-cffi-bindings==25.1.0
arrow==1.4.0
asttokens==3.0.0
async-lru==2.0.5
attrs==25.4.0
babel==2.17.0
backcall==0.2.0
beautifulsoup4==4.14.2
bleach==6.2.0
blinker==1.9.0
cachetools==6.2.1
certifi==2025.10.5
cffi==2.0.0
charset-normalizer==3.4.4
click==8.3.0
colorama==0.4.6
comm==0.2.3
contourpy==1.3.3
cvzone==1.6.1
cycler==0.12.1
Cython==3.1.5
dataclasses-json==0.6.7
debugpy==1.8.17
decorator==5.2.1
deep-sort-realtime==1.3.2
defusedxml==0.7.1
dlib @ file:///C:/bld/dlib-split_1761791650486/work
easydict==1.13
easyocr==1.7.2
executing==2.2.1
face-recognition==1.3.0
face_recognition_models==0.3.0
fastjsonschema==2.21.2
filelock==3.20.0
filterpy==1.4.5
Flask==3.1.2
fonttools==4.60.1
fqdn==1.5.1
fsspec==2025.9.0
google-auth==2.41.1
google-auth-oauthlib==1.2.2
grpcio==1.76.0
h11==0.16.0
h5py==3.15.1
httpcore==1.0.9
httpx==0.28.1
hydra-core==1.3.2
idna==3.11
imageio==2.37.0
importlib_metadata==8.7.0
importlib_resources==6.5.2
iniconfig==2.3.0
ipykernel==7.0.1
ipython==9.6.0
ipython-genutils==0.2.0
ipython_pygments_lexers==1.1.1
ipywidgets==8.1.7
isoduration==20.11.0
itsdangerous==2.2.0
jedi==0.19.2
Jinja2==3.1.6
joblib==1.5.2
json5==0.12.1
jsonpointer==3.0.0
jsonschema==4.25.1
jsonschema-specifications==2025.9.1
jupyter==1.1.1
jupyter-console==6.6.3
jupyter-events==0.12.0
jupyter-lsp==2.3.0
jupyter_client==8.6.3
jupyter_core==5.9.1
jupyter_server==2.17.0
jupyter_server_terminals==0.5.3
jupyterlab==4.4.10
jupyterlab_pygments==0.3.0
jupyterlab_server==2.28.0
jupyterlab_widgets==3.0.15
kiwisolver==1.4.9
labelImg==1.8.6
lap @ file:///D:/bld/lap_1756649018065/work
lark==1.3.0
lazy_loader==0.4
llvmlite==0.45.1
loguru==0.7.3
lxml==6.0.2
lz4==4.4.5
Markdown==3.9
MarkupSafe==3.0.3
marshmallow==3.26.1
matplotlib==3.10.7
matplotlib-inline==0.1.7
mistune==3.1.4
motmetrics==1.4.0
mpmath==1.3.0
mypy_extensions==1.1.0
nbclassic==1.3.3
nbclient==0.10.2
nbconvert==7.16.6
nbformat==5.10.4
nest-asyncio==1.6.0
networkx==3.5
ninja==1.13.0
notebook==7.4.7
notebook_shim==0.2.4
numba==0.62.1
numpy==2.2.6
oauthlib==3.3.1
omegaconf==2.3.0
onemetric==0.1.2
opencv-python==4.12.0.88
opencv-python-headless==4.12.0.88
overrides==7.7.0
packaging==25.0
pafy==0.5.5
pandas==2.3.3
pandocfilters==1.5.1
parso==0.8.5
pickleshare==0.7.5
pillow==12.0.0
platformdirs==4.5.0
pluggy==1.6.0
polars==1.34.0
polars-runtime-32==1.34.0
prometheus_client==0.23.1
prompt_toolkit==3.0.52
protobuf==6.33.0
psutil==7.1.1
pure_eval==0.2.3
pyasn1==0.6.1
pyasn1_modules==0.4.2
pyclipper==1.3.0.post6
pycocotools==2.0.10
pycparser==2.23
pydantic==2.12.5
pydantic_core==2.41.5
Pygments==2.19.2
pyparsing==3.2.5
PyQt5==5.15.11
PyQt5-Qt5==5.15.2
PyQt5_sip==12.17.1
pyrsistent==0.20.0
pytest==9.0.1
python-bidi==0.6.7
python-dateutil==2.9.0.post0
python-json-logger==4.0.0
pytube==15.0.0
pytz==2025.2
PyWavelets==1.9.0
pywin32==311
pywinpty==3.0.2
PyYAML==6.0.3
pyzmq==27.1.0
qtconsole==5.7.0
QtPy==2.4.3
referencing==0.37.0
requests==2.32.5
requests-oauthlib==2.0.0
rfc3339-validator==0.1.4
rfc3986-validator==0.1.1
rfc3987-syntax==1.1.0
rpds-py==0.28.0
rsa==4.9.1
Rx==3.2.0
scikit-image==0.25.2
scikit-learn==1.7.2
scipy==1.16.3
seaborn==0.13.2
Send2Trash==1.8.3
sentry-sdk==2.42.1
shapely==2.1.2
six==1.17.0
sniffio==1.3.1
soupsieve==2.8
stack-data==0.6.3
supervision==0.26.1
sympy==1.14.0
tabulate==0.9.0
tensorboard==2.20.0
tensorboard-data-server==0.7.2
terminado==0.18.1
thop==0.1.1.post2209072238
threadpoolctl==3.6.0
tifffile==2025.10.16
tinycss2==1.4.0
torch==2.9.0
torchaudio==2.9.0+cpu
torchvision==0.24.0
tornado==6.5.2
tqdm==4.67.1
traitlets==5.14.3
typing-inspect==0.9.0
typing-inspection==0.4.2
typing_extensions==4.15.0
tzdata==2025.2
ultralytics==8.3.220
ultralytics-thop==2.0.17
uri-template==1.3.0
urllib3==2.5.0
wcwidth==0.2.14
webcolors==24.11.1
webencodings==0.5.1
websocket-client==1.9.0
websockets==15.0.1
Werkzeug==3.1.3
widgetsnbextension==4.0.14
win32_setctime==1.2.0
xmltodict==1.0.2
youtube-dl==2021.12.17
zipp==3.23.0
```

ملاحظة أخيرة:
- قمت بتشغيل الاختبارات وتحققًا سريعًا من `run_system.py --help` فقط (لم أبدأ الخدمات الفعلية: `ingestion`, `detection`, `ui`).
- إذا أردت، أستطيع تشغيل النظام بالكامل (مع تسجيل كامل للمخرجات) لكن ذلك سيشغّل عمليات خلفية ويتطلب توفر خدماتٍ خارجية (مثل Redis) وملفات النماذج؛ هل ترغب أن أُجري تشغيلًا متكاملًا الآن؟
