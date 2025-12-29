import subprocess
import sys
import time
import os
import signal
import threading
import socket

# ==============================================================================
# BASE CONFIGURATION
# ==============================================================================
# تحديد المسار الحالي كـ PYTHONPATH لكي تعمل الاستيرادات
CWD = os.getcwd()
BASE_ENV = os.environ.copy()
BASE_ENV["PYTHONPATH"] = CWD
BASE_ENV["PYTHONUNBUFFERED"] = "1"
BASE_ENV["TRANSPORT_TYPE"] = "simple"
BASE_ENV["BUS_HOST"] = "localhost"
BASE_ENV["BUS_PORT"] = "5555"

# Global Process List
processes = []

# ==============================================================================
# 1. SIMPLE BUS BROKER (INFRASTRUCTURE)
# ==============================================================================
def run_simple_broker(host, port):
    """
    Simulates the Transport Layer (Simple TCP Broker).
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(5)
        print(f"[BROKER] 🟢 Running on {host}:{port}")
    except OSError:
        print(f"[BROKER] 🔴 Port {port} is busy.")
        return

    clients = []

    def handle_client(conn, addr):
        clients.append(conn)
        try:
            while True:
                data = conn.recv(4096)
                if not data: break
                # Broadcast (Pub/Sub Simulation)
                for c in clients:
                    if c != conn:
                        try:
                            c.sendall(data)
                        except: pass
        except: pass
        finally:
            if conn in clients: clients.remove(conn)
            conn.close()

    while True:
        client, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
        t.start()

# ==============================================================================
# 2. SERVICE LAUNCHER
# ==============================================================================
def start_service(name, module, specific_env_vars):
    """
    Starts a service as a subprocess with its own specific Environment Variables.
    """
    print(f"[SYSTEM] 🚀 Starting {name}...")
    
    # Merge Base Env with Service Specific Env
    service_env = BASE_ENV.copy()
    service_env.update(specific_env_vars)
    
    p = subprocess.Popen(
        [sys.executable, "-m", module],
        env=service_env,
        cwd=CWD
    )
    processes.append(p)
    return p

def cleanup(signum, frame):
    print("\n[SYSTEM] 🛑 Shutting down all services...")
    for p in processes:
        p.terminate()
    sys.exit(0)

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print(">>> SYSTEM STARTUP: Stage 5 Architecture (Real Services) <<<")
    
    # 1. Start Broker
    broker_thread = threading.Thread(
        target=run_simple_broker, 
        args=(BASE_ENV["BUS_HOST"], int(BASE_ENV["BUS_PORT"])),
        daemon=True
    )
    broker_thread.start()
    time.sleep(1) 

    # 2. Start Memory Service
    # Config: Requires "ring" backend
    memory_env = {
        "MEMORY_BACKEND": "ring",
        "BUFFER_SIZE_BYTES": "50000000", # 50MB
        "MAX_FRAME_SIZE_BYTES": "1000000"
    }
    start_service("Memory Service", "memory.server", memory_env)
    time.sleep(2) # Give Memory time to bind port 6000

    # 3. Start Ingestion Service
    # Config: Requires "http" backend to talk to Memory Service
    # Using '0' for webcam, or replace with RTSP URL or Video Path
    ingestion_env = {
        "RTSP_URL": "0", 
        "STREAM_ID": "cam_01",
        "CAMERA_ID": "gate_north",
        "TARGET_FPS": "5",
        "FRAME_WIDTH": "640",
        "FRAME_HEIGHT": "480",
        "MEMORY_BACKEND": "http" # Note: Client uses HTTP, Server uses Ring
    }
    start_service("Ingestion Service", "ingestion.main", ingestion_env)

    # 4. Start Detection Service
    # Config: "Blind" to Memory backend, only needs shape
    detection_env = {
        "MODEL_NAME": "yolo_nano",
        "MODEL_VERSION": "1.0",
        "MODEL_HASH": "xyz",
        "MODEL_PATH": "dummy.pt",
        "INFERENCE_TIMEOUT": "5",
        "INPUT_TOPIC": "frames.v1",
        "OUTPUT_TOPIC": "detections.v1",
        "DEBUG": "true"
    }
    start_service("Detection Service", "detection.main", detection_env)

    # 5. Start Results Service
    # Config: Visualizer
    results_env = {
        "OUTPUT_TOPIC": "detections.v1",
        "FRAME_WIDTH": "640",
        "FRAME_HEIGHT": "480"
    }
    start_service("Results Service", "results.main", results_env)

    # Keep alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()