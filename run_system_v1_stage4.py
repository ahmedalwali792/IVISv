# run_system_v1_stage4.py
import subprocess
import time
import os
import sys

# =========================================================
# ORCHESTRATOR FOR V1 + STAGE 4 (Full Pipeline)
# =========================================================

# ------------------------------------------------------------------------------
# Project Root (Fixes ModuleNotFoundError)
# ------------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# Ensure logs dir
os.makedirs("logs", exist_ok=True)

processes = []

def start_process(name, command, env=None):
    print(f"🚀 Starting {name}...")
    out = open(f"logs/{name}.out", "w")
    err = open(f"logs/{name}.err", "w")
    p = subprocess.Popen(command, env=env, stdout=out, stderr=err)
    processes.append(p)
    return p

try:
    print("=== Video Analytics: v1.0 + Stage 4 (Result Plane) ===")
    
    # ------------------------------------------------------------------------------
    # Base Environment (Clean + PYTHONPATH)
    # ------------------------------------------------------------------------------
    base_env = os.environ.copy()
    # Critical Fix: Add project root to PYTHONPATH so sub-processes can import modules
    base_env["PYTHONPATH"] = PROJECT_ROOT 
    
    # 1. Infrastructure
    # Added "-u" for unbuffered output (Real-time logs)
    start_process("bus", [sys.executable, "-u", "infrastructure/bus.py"], env=base_env)
    time.sleep(1)

    # 2. Memory (Node A)
    env_mem = base_env.copy()
    env_mem.update({
        "MEMORY_BACKEND": "ring",
        "MEMORY_HOST": "localhost",
        "MEMORY_PORT": "6000",
        "BUFFER_SIZE_BYTES": "50000000",
        "MAX_FRAME_SIZE_BYTES": "1000000"
    })
    start_process("memory", [sys.executable, "-u", "memory/server.py"], env=env_mem)
    time.sleep(1)

    # 3. Ingestion (Node A)
    env_ingest = base_env.copy()
    env_ingest.update({
        "MEMORY_BACKEND": "http",
        "RTSP_URL": "0", # Camera 0
        "STREAM_ID": "stream_main",
        "CAMERA_ID": "cam_01",
        "TARGET_FPS": "15",
        "FRAME_WIDTH": "640",
        "FRAME_HEIGHT": "480",
        "BUS_HOST": "localhost",
        "BUS_PORT": "5555"
    })
    start_process("ingestion", [sys.executable, "-u", "ingestion/main.py"], env=env_ingest)

    # 4. Detection (Node B)
    env_detect = base_env.copy()
    env_detect.update({
        "MODEL_NAME": "YOLO_Nano",
        "MODEL_VERSION": "1.0",
        "MODEL_HASH": "idxxx",
        "MODEL_PATH": "model.pt",
        "INFERENCE_TIMEOUT": "2",
        "INPUT_TOPIC": "frames",
        "OUTPUT_TOPIC": "detections",
        "BUS_HOST": "localhost",
        "BUS_PORT": "5555",
        "MEMORY_HOST": "localhost",
        "MEMORY_PORT": "6000"
    })
    start_process("detection", [sys.executable, "-u", "detection/main.py"], env=env_detect)

    # 5. Result Plane (Stage 4 - New Node)
    # This is the ONLY new addition to the runtime
    env_result = base_env.copy()
    env_result.update({
        "BUS_HOST": "localhost",
        "BUS_PORT": "5555",
        "OUTPUT_TOPIC": "detections",
        "RESULT_LOG_FILE": "logs/detections.jsonl",
        "FRAME_WIDTH": "640", # For canvas setup only
        "FRAME_HEIGHT": "480"
    })
    start_process("result_plane", [sys.executable, "-u", "results/main.py"], env=env_result)

    print("\n✅ Full Pipeline Running (Ingestion -> Memory -> Detection -> Results)")
    print("   Check 'logs/result_plane.out' or the visual window.")
    
    while True:
        time.sleep(1)
        for p in processes:
            if p.poll() is not None:
                print(f"⚠️ Process died! Code: {p.returncode}")
                raise KeyboardInterrupt

except KeyboardInterrupt:
    print("\n🛑 Shutting down...")
    for p in processes:
        p.terminate()