# FILE: ingestion/main.py
# ------------------------------------------------------------------------------
import sys
import os
import time

from ingestion.capture.decoder import Decoder
from ingestion.capture.reader import Reader
from ingestion.capture.rtsp_client import RTSPClient
from ingestion.config import Config
from ingestion.errors.fatal import ConfigError, FatalError
from ingestion.frame.anchor import Anchor
from ingestion.frame.id import FrameIdentity
from ingestion.frame.normalizer import Normalizer
from ingestion.frame.selector import Selector
from ingestion.heartbeat import Heartbeat
from ingestion.memory.writer import Writer
from ingestion.metrics.counters import Metrics
from ingestion.runtime import Runtime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ingestion.ipc import HTTPMemoryBackend, SocketPublisher
    IPC_AVAILABLE = True
except ImportError:
    IPC_AVAILABLE = False

def main():
    print(">>> Ingestion Service: Initializing (Frozen v1.0) <<<")
    
    try:
        conf = Config()
    except ConfigError as e:
        print(f"FATAL: Config Error - {e.message}")
        sys.exit(1)

    runtime = Runtime()
    metrics = Metrics()
    
    try:
        rtsp = RTSPClient(conf.rtsp_url)
        reader = Reader(rtsp)
        decoder = Decoder()
        selector = Selector(conf.target_fps)
        normalizer = Normalizer(conf.resolution)
        anchor = Anchor()
        
        # --- Backend Selection (Strict) ---
        if conf.memory_backend == "http":
            if not IPC_AVAILABLE:
                raise FatalError("IPC modules missing, cannot start HTTP backend")
            print("[Topology] Using HTTP Memory Backend (Port 6000)")
            backend_impl = HTTPMemoryBackend(host="localhost", port=6000)
        else:
             raise FatalError(f"Unsupported MEMORY_BACKEND for Stage 3: {conf.memory_backend}")

        writer = Writer(backend_impl)
        
        # --- Publisher Selection ---
        if IPC_AVAILABLE:
            print("[Topology] Using Socket Publisher (Port 5555)")
            publisher = SocketPublisher(conf, host="localhost", port=5555)
        else:
            raise FatalError("IPC modules missing, cannot start Publisher")

        heartbeat = Heartbeat(conf.stream_id)
        
        rtsp.connect()

    except FatalError as e:
        print(f"FATAL: Startup Failed - {e.message}")
        sys.exit(1)

    print(f">>> Ingestion Running | Stream: {conf.stream_id} <<<")

    while runtime.should_continue():
        try:
            heartbeat.tick()
            
            packet = reader.next_packet()
            
            if packet is None:
                raise FatalError("Source EOF or Connection Lost")

            if packet.pts <= 0:
                metrics.inc_dropped_pts()
                continue

            raw_frame = decoder.decode(packet)
            if raw_frame is None:
                metrics.inc_dropped_corrupt()
                continue
            
            metrics.inc_captured()

            if not selector.allow(packet.pts):
                metrics.inc_dropped_fps()
                continue

            clean_frame = normalizer.process(raw_frame)
            fingerprint = anchor.generate(clean_frame)
            identity = FrameIdentity(conf.stream_id, packet.pts, fingerprint)

            ref = writer.write(clean_frame, identity)
            
            publisher.publish(identity, packet.timestamp, ref)
            
            metrics.inc_processed()
        
        except FatalError as e:
            print(f"!!! FATAL ERROR !!! {e.message} | Context: {e.context}")
            break

        except Exception as e:
            print(f"!!! UNHANDLED CRASH !!! {str(e)}")
            import traceback
            traceback.print_exc()
            break

    rtsp.close()
    runtime.shutdown()
    sys.exit(1)

if __name__ == "__main__":
    main()