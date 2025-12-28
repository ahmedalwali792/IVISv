# ------------------------------------------------------------------------------
# FILE: run_system.py
# ------------------------------------------------------------------------------
import subprocess
import time
import os
import sys

# ------------------------------------------------------------------------------
# Project Root (IMPORTANT)
# ------------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# ------------------------------------------------------------------------------
# Ensure logs directory exists
# ------------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)

processes = []

def start_process(name, command, env=None):
    print(f"🚀 Starting {name}...")
    out = open(f"logs/{name}.out", "w")
    err = open(f"logs/{name}.err", "w")
    p = subprocess.Popen(
        command,
        env=env,
        stdout=out,
        stderr=err
    )
    processes.append(p)
    return p

try:
    print("=== Starting Video Analytics System (v1.0 Frozen - Patched) ===")

    # ------------------------------------------------------------------------------
    # Base Environment (Clean + PYTHONPATH)
    # ------------------------------------------------------------------------------
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = PROJECT_ROOT

    # ------------------------------------------------------------------------------
    # 1. Bus (DEV Infra)
    # ------------------------------------------------------------------------------
    start_process(
        "bus",
        [sys.executable, "infrastructure/bus.py"],
        env=base_env
    )
    time.sleep(1)

    # ------------------------------------------------------------------------------
    # 2. Memory Service
    # ------------------------------------------------------------------------------
    env_memory = base_env.copy()
    env_memory["MEMORY_BACKEND"] = "ring"
    env_memory["MEMORY_HOST"] = "localhost"
    env_memory["MEMORY_PORT"] = "6000"
    env_memory["BUFFER_SIZE_BYTES"] = "50000000"
    env_memory["MAX_FRAME_SIZE_BYTES"] = "1000000"

    start_process(
        "memory",
        [sys.executable, "memory/server.py"],
        env=env_memory
    )
    time.sleep(1)

    # ------------------------------------------------------------------------------
    # 3. Ingestion Service
    # ------------------------------------------------------------------------------
    env_ingestion = base_env.copy()
    env_ingestion["MEMORY_BACKEND"] = "http"
    env_ingestion["MEMORY_HOST"] = "localhost"
    env_ingestion["MEMORY_PORT"] = "6000"

    env_ingestion["RTSP_URL"] = "0"
    env_ingestion["STREAM_ID"] = "cam_01_main"
    env_ingestion["CAMERA_ID"] = "cam_01"
    env_ingestion["TARGET_FPS"] = "15"

    env_ingestion["BUS_HOST"] = "localhost"
    env_ingestion["BUS_PORT"] = "5555"
    env_ingestion["FRAME_WIDTH"] = "640"
    env_ingestion["FRAME_HEIGHT"] = "480"

    start_process(
        "ingestion",
        [sys.executable, "ingestion/main.py"],
        env=env_ingestion
    )

    # ------------------------------------------------------------------------------
    # 4. Detection Service
    # ------------------------------------------------------------------------------
    env_detection = base_env.copy()
    env_detection["MODEL_NAME"] = "YOLO_Nano_Mock"
    env_detection["MODEL_VERSION"] = "v1"
    env_detection["MODEL_HASH"] = "mock_hash_123"
    env_detection["MODEL_PATH"] = "./models/yolo.pt"
    env_detection["INFERENCE_TIMEOUT"] = "2"
    env_detection["DEBUG"] = "true"
    env_detection["BUS_HOST"] = "localhost"
    env_detection["BUS_PORT"] = "5555"
    env_detection["MEMORY_HOST"] = "localhost"
    env_detection["MEMORY_PORT"] = "6000"


    start_process(
        "detection",
        [sys.executable, "detection/main.py"],
        env=env_detection
    )

    print("\n✅ System Running!")
    print(f"   Logs are being written to: {os.path.abspath('logs/')}")
    print("   Press Ctrl+C to stop all services.\n")

    # ------------------------------------------------------------------------------
    # Monitor Loop
    # ------------------------------------------------------------------------------
    while True:
        time.sleep(1)
        for p in processes:
            if p.poll() is not None:
                print(f"⚠️ Process died unexpectedly! Return Code: {p.returncode}")
                raise KeyboardInterrupt

except KeyboardInterrupt:
    print("\n🛑 Stopping System...")
    for p in processes:
        p.terminate()
    print("All processes terminated.")
