# ------------------------------------------------------------------------------
# FILE: run_system.py
# ------------------------------------------------------------------------------
import argparse
import json
import os
import platform
import subprocess
import sys
import time
from ivis_logging import setup_logging
from common.settings import SETTINGS

# ------------------------------------------------------------------------------
# Project Root (IMPORTANT)
# ------------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# ------------------------------------------------------------------------------
# Ensure logs directory exists
# ------------------------------------------------------------------------------
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Always use the current interpreter to avoid mismatched environments.
PYTHON_EXE = sys.executable
logger = setup_logging("orchestrator")
logger.info("Using Python executable for services: %s", PYTHON_EXE)


class ServiceProcess:
    def __init__(self, name, command, env):
        self.name = name
        self.command = command
        self.env = env
        self.process = None
        self.out_file = None
        self.err_file = None
        self.restarts = 0
        self.max_restarts = 5
        self.last_restart_time = 0
    
    def start(self):
        logger.info(f"Starting service: {self.name}")
        self.out_file = open(os.path.join(LOG_DIR, f"{self.name}.out"), "a") # append mode for restarts
        self.err_file = open(os.path.join(LOG_DIR, f"{self.name}.err"), "a")
        
        # Ensure child processes can import project-top-level modules
        process_env = os.environ.copy()
        if self.env:
            process_env.update(self.env)
        existing = process_env.get("PYTHONPATH")
        if existing:
            process_env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + existing
        else:
            process_env["PYTHONPATH"] = PROJECT_ROOT
            
        try:
            self.process = subprocess.Popen(
                self.command,
                env=process_env,
                cwd=PROJECT_ROOT,
                stdout=self.out_file,
                stderr=self.err_file,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start {self.name}: {e}")
            return False

    def is_alive(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self._close_files()

    def _close_files(self):
        try:
            if self.out_file: self.out_file.close()
            if self.err_file: self.err_file.close()
        except Exception:
            pass
        self.out_file = None
        self.err_file = None

    def check_and_restart(self):
        if self.process is None:
            return # Not started yet
        
        ret_code = self.process.poll()
        if ret_code is not None:
            logger.warning(f"Service {self.name} died with return code {ret_code}")
            
            # Reset restart count if it's been alive for a while (> 60s)
            now = time.time()
            if now - self.last_restart_time > 60:
                self.restarts = 0
            
            if self.restarts < self.max_restarts:
                self.restarts += 1
                wait_time = min(self.restarts * 2, 30)
                logger.info(f"Restarting {self.name} in {wait_time}s (Attempt {self.restarts}/{self.max_restarts})")
                self._close_files()
                time.sleep(wait_time)
                self.last_restart_time = time.time()
                self.start()
            else:
                logger.error(f"Service {self.name} failed too many times. Giving up.")
                return False # Failed permanently
        return True # Alive or successfully restarted


def _resolve_source(args, base_env):
    if args.webcam is not None:
        source = str(args.webcam)
        source_type = "webcam"
    else:
        source = args.source or base_env.get("RTSP_URL") or "0"
        source_type = args.source_type or "auto"

    source = source.strip()
    expanded = os.path.abspath(os.path.expanduser(source))
    is_url = source.lower().startswith(("rtsp://", "http://", "https://"))
    file_exists = os.path.isfile(expanded)

    if source_type == "file":
        if not file_exists:
            raise ValueError(f"Source file not found: {expanded}")
        return expanded, "file"
    if source_type == "webcam":
        if not source.isdigit():
            raise ValueError("Webcam source must be a numeric index (e.g. 0)")
        return source, "webcam"
    if source_type == "rtsp":
        return source, "rtsp"

    # auto detection
    if file_exists:
        return expanded, "file"
    if source.isdigit():
        return source, "webcam"
    if is_url:
        return source, "rtsp"
    # Fall back to raw string; ingestion will validate.
    return source, "rtsp"

def _load_config_file(path: str) -> dict:
    if not os.path.exists(path):
        raise ValueError(f"Config file not found: {path}")
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    with open(path, "r", encoding="utf-8") as handle:
        if ext in (".json",):
            return json.load(handle)
        if ext in (".yaml", ".yml"):
            try:
                import yaml
            except Exception as exc:
                raise ValueError("PyYAML is required to load YAML config files") from exc
            return yaml.safe_load(handle) or {}
    raise ValueError("Unsupported config file format (use .json or .yaml)")


def _apply_env_map(target_env: dict, values: dict):
    for key, value in values.items():
        if value is None:
            continue
        target_env[key] = str(value)


def main(argv=None):
    print("=== Starting Video Analytics System (v1.1 Robust - Patched) ===")

    # ------------------------------------------------------------------------------
    # Base Environment (Clean)
    # ------------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="IVISv system launcher")
    parser.add_argument("--source", help="Video source (file path, RTSP URL, or webcam index)")
    parser.add_argument("--source-type", choices=["auto", "file", "webcam", "rtsp"], default="auto")
    parser.add_argument("--webcam", type=int, help="Webcam index (overrides --source)")
    parser.add_argument("--target-fps", type=int, default=15)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--frame-color", choices=["bgr", "rgb"], default="bgr")
    parser.add_argument("--bus", choices=["zmq", "tcp"], default="zmq")
    parser.add_argument("--config", help="Path to JSON/YAML config file")
    loop_group = parser.add_mutually_exclusive_group()
    loop_group.add_argument("--loop", action="store_true", help="Loop local video files")
    loop_group.add_argument("--no-loop", action="store_true", help="Disable looping for local video files")
    args = parser.parse_args()

    base_env = os.environ.copy()
    # seed environment from centralized settings where appropriate
    try:
        base_env.update(SETTINGS.as_env())
    except Exception:
        pass
    config_data = None
    if args.config:
        config_data = _load_config_file(args.config)
        if isinstance(config_data, dict):
            if "env" in config_data and isinstance(config_data["env"], dict):
                _apply_env_map(base_env, config_data["env"])
            elif "ingestion" not in config_data and "detection" not in config_data and "ui" not in config_data:
                _apply_env_map(base_env, config_data)

    services = []

    # ------------------------------------------------------------------------------
    # 2. Ingestion Service
    # ------------------------------------------------------------------------------
    env_ingestion = base_env.copy()
    env_ingestion["MEMORY_BACKEND"] = "shm"
    env_ingestion["SHM_CACHE_SECONDS"] = "30"
    env_ingestion["SHM_OWNER"] = "1"
    if isinstance(config_data, dict) and isinstance(config_data.get("ingestion"), dict):
        _apply_env_map(env_ingestion, config_data["ingestion"])

    try:
        source, source_type = _resolve_source(args, base_env)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
    env_ingestion["RTSP_URL"] = source
    env_ingestion["STREAM_ID"] = "cam_01_main"
    env_ingestion["CAMERA_ID"] = "cam_01"
    env_ingestion["TARGET_FPS"] = str(args.target_fps)

    env_ingestion["BUS_TRANSPORT"] = args.bus
    env_ingestion["ZMQ_PUB_ENDPOINT"] = "tcp://localhost:5555"
    env_ingestion["ZMQ_RESULTS_SUB_ENDPOINT"] = "tcp://localhost:5557"
    env_ingestion["FRAME_WIDTH"] = str(args.width)
    env_ingestion["FRAME_HEIGHT"] = str(args.height)
    source_color = args.frame_color or base_env.get("SOURCE_COLOR") or "bgr"
    env_ingestion["SOURCE_COLOR"] = source_color
    env_ingestion["FRAME_COLOR_SPACE"] = base_env.get("FRAME_COLOR_SPACE", "bgr")
    env_ingestion["SELECTOR_MODE"] = "clock"
    env_ingestion["ADAPTIVE_FPS"] = "true"
    env_ingestion["ADAPTIVE_MIN_FPS"] = "5"
    env_ingestion["ADAPTIVE_MAX_FPS"] = env_ingestion["TARGET_FPS"]
    env_ingestion["ADAPTIVE_SAFETY"] = "1.3"
    if args.loop:
        loop_enabled = True
    elif args.no_loop:
        loop_enabled = False
    else:
        loop_enabled = source_type == "file"
    if loop_enabled:
        env_ingestion["VIDEO_LOOP"] = "true"

    slot_size = int(env_ingestion["FRAME_WIDTH"]) * int(env_ingestion["FRAME_HEIGHT"]) * 3
    cache_seconds = float(env_ingestion.get("SHM_CACHE_SECONDS", "30"))
    cache_fps = float(env_ingestion["TARGET_FPS"])
    slot_count = max(1, int(cache_fps * cache_seconds))
    env_ingestion["SHM_CACHE_FPS"] = env_ingestion["TARGET_FPS"]
    env_ingestion["SHM_BUFFER_BYTES"] = str(slot_size * slot_count)
    env_ingestion["SHM_NAME"] = f"ivis_shm_data_{slot_size}_{slot_count}"
    env_ingestion["SHM_META_NAME"] = f"ivis_shm_meta_{slot_size}_{slot_count}"

    ingestion_svc = ServiceProcess(
        "ingestion",
        [PYTHON_EXE, "-m", "ingestion.main"],
        env=env_ingestion,
    )
    services.append(ingestion_svc)

    # ------------------------------------------------------------------------------
    # 3. Detection Service
    # ------------------------------------------------------------------------------
    env_detection = base_env.copy()
    env_detection["MODEL_NAME"] = "YOLO11"
    env_detection["MODEL_VERSION"] = "v11"
    env_detection["MODEL_HASH"] = "yolo11"
    default_model = os.path.join(PROJECT_ROOT, "models", "yolo.pt")
    shipped_model = os.path.join(PROJECT_ROOT, "yolo11n.pt")
    if os.path.exists(default_model):
        env_detection["MODEL_PATH"] = default_model
    elif os.path.exists(shipped_model):
        env_detection["MODEL_PATH"] = os.path.abspath(shipped_model)
    else:
        env_detection["MODEL_PATH"] = default_model
        print(f"[WARN] No model file found at '{default_model}' or '{shipped_model}'.")
    env_detection["INFERENCE_TIMEOUT"] = "2"
    env_detection["DEBUG"] = "true"
    env_detection["MODEL_DEVICE"] = "auto"
    env_detection["MODEL_HALF"] = "false"
    env_detection["MODEL_IMG_SIZE"] = "640"
    env_detection["MODEL_CONF"] = "0.25"
    env_detection["MODEL_IOU"] = "0.5"
    reid_default = os.path.join(PROJECT_ROOT, "models", "reid", "osnet_x0_25.pth")
    if os.path.exists(reid_default):
        env_detection["REID_MODEL_PATH"] = reid_default
    else:
        env_detection["REID_ALLOW_FALLBACK"] = "true"
        print(f"[WARN] ReID weights not found at '{reid_default}'. Falling back without custom weights.")
    env_detection["BUS_TRANSPORT"] = args.bus
    env_detection["ZMQ_SUB_ENDPOINT"] = env_ingestion.get("ZMQ_PUB_ENDPOINT", "tcp://localhost:5555")
    env_detection["ZMQ_RESULTS_PUB_ENDPOINT"] = "tcp://localhost:5557"
    env_detection["MEMORY_BACKEND"] = "shm"
    env_detection["SHM_OWNER"] = "0"
    env_detection["SHM_NAME"] = env_ingestion["SHM_NAME"]
    env_detection["SHM_META_NAME"] = env_ingestion["SHM_META_NAME"]
    env_detection["SHM_BUFFER_BYTES"] = env_ingestion["SHM_BUFFER_BYTES"]
    env_detection["SHM_CACHE_SECONDS"] = env_ingestion.get("SHM_CACHE_SECONDS", "30")
    env_detection["SHM_CACHE_FPS"] = env_ingestion.get("SHM_CACHE_FPS", env_ingestion["TARGET_FPS"])
    env_detection["FRAME_WIDTH"] = env_ingestion["FRAME_WIDTH"]
    env_detection["FRAME_HEIGHT"] = env_ingestion["FRAME_HEIGHT"]
    env_detection["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env_detection["FRAME_COLOR_SPACE"] = env_ingestion["FRAME_COLOR_SPACE"]
    env_detection["MAX_FRAME_AGE_MS"] = "1000"
    env_detection["TORCH_NUM_THREADS"] = "4"
    env_detection["TORCH_NUM_INTEROP_THREADS"] = "2"
    if isinstance(config_data, dict) and isinstance(config_data.get("detection"), dict):
        _apply_env_map(env_detection, config_data["detection"])

    detection_svc = ServiceProcess(
        "detection",
        [PYTHON_EXE, "-m", "detection.main"],
        env=env_detection,
    )
    services.append(detection_svc)

    # --------------------------------------------------------------------------
    # 4. UI Service (Live View)
    # --------------------------------------------------------------------------
    env_ui = base_env.copy()
    env_ui["DEBUG"] = "true"
    env_ui["ZMQ_SUB_ENDPOINT"] = env_ingestion.get("ZMQ_PUB_ENDPOINT", "tcp://localhost:5555")
    env_ui["ZMQ_RESULTS_SUB_ENDPOINT"] = env_detection.get("ZMQ_RESULTS_PUB_ENDPOINT", "tcp://localhost:5557")
    env_ui["SHM_OWNER"] = "0"
    env_ui["STREAM_ID"] = env_ingestion["STREAM_ID"]
    env_ui["CAMERA_ID"] = env_ingestion["CAMERA_ID"]
    env_ui["SHM_NAME"] = env_ingestion["SHM_NAME"]
    env_ui["SHM_META_NAME"] = env_ingestion["SHM_META_NAME"]
    env_ui["SHM_BUFFER_BYTES"] = env_ingestion["SHM_BUFFER_BYTES"]
    env_ui["SHM_CACHE_SECONDS"] = env_ingestion.get("SHM_CACHE_SECONDS", "30")
    env_ui["SHM_CACHE_FPS"] = env_ingestion.get("SHM_CACHE_FPS", env_ingestion["TARGET_FPS"])
    env_ui["FRAME_WIDTH"] = env_ingestion["FRAME_WIDTH"]
    env_ui["FRAME_HEIGHT"] = env_ingestion["FRAME_HEIGHT"]
    env_ui["FRAME_COLOR_SPACE"] = env_ingestion["FRAME_COLOR_SPACE"]
    if isinstance(config_data, dict) and isinstance(config_data.get("ui"), dict):
        _apply_env_map(env_ui, config_data["ui"])

    ui_svc = ServiceProcess(
        "ui",
        [PYTHON_EXE, "-m", "ui.live_view"],
        env=env_ui,
    )
    services.append(ui_svc)

    # ------------------------------------------------------------------------------
    # Start All
    # ------------------------------------------------------------------------------
    for svc in services:
        svc.start()

    print("\nSystem Running!")
    print(f"   Logs are being written to: {os.path.abspath('logs/')}")
    print("   UI is available at: http://127.0.0.1:8080")
    print("   Press Ctrl+C to stop all services.\n")

    # ------------------------------------------------------------------------------
    # Monitor Loop
    # ------------------------------------------------------------------------------
    try:
        while True:
            time.sleep(1)
            active_count = 0
            for svc in services:
                if not svc.check_and_restart():
                    logger.error(f"Service {svc.name} has failed permanently.")
                else:
                    active_count += 1
            
            if active_count == 0:
                print("All services have failed. Exiting.")
                break
                
    except KeyboardInterrupt:
        print("\nStopping System...")
    finally:
        for svc in services:
            svc.stop()
        print("All processes terminated.")

if __name__ == "__main__":
    main()
