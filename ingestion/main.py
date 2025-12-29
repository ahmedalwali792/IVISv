# [2025-12-29] ingestion/main.py
import sys
import os
import time
from ingestion.config import Config
from ingestion.runtime import Runtime
from ingestion.metrics.counters import Metrics
from ingestion.capture.rtsp_client import RTSPClient
from ingestion.capture.reader import Reader
from ingestion.capture.decoder import Decoder
from ingestion.frame.selector import Selector
from ingestion.frame.normalizer import Normalizer
from ingestion.frame.anchor import Anchor
from ingestion.frame.id import FrameIdentity
from ingestion.memory.writer import Writer
from ingestion.ipc import HTTPMemoryBackend
from ingestion.publish.stream import StreamPublisher
from ingestion.publish.heartbeat import Heartbeat
from ingestion.errors.fatal import FatalError, ConfigError

# Import Infrastructure Adapters (Stage 5)
try:
    from infrastructure.transport.factory import TransportFactory
except ImportError:
    print("FATAL: Infrastructure missing")
    sys.exit(1)

def main():
    print(">>> Ingestion Service: Initializing (Stage 0.9.2 Isolated / Stage 5 Compliant) <<<")
    
    try:
        conf = Config()
    except ConfigError as e:
        print(f"FATAL: Config Error - {e.message}")
        sys.exit(1)

    runtime = Runtime()
    metrics = Metrics()
    
    try:
        # Note: If URL is '0', it will open local webcam
        rtsp = RTSPClient(conf.rtsp_url)
        reader = Reader(rtsp)
        decoder = Decoder()
        selector = Selector(conf.target_fps)
        normalizer = Normalizer(conf.resolution)
        anchor = Anchor()
        
        # --- Memory Backend ---
        if conf.memory_backend == "http":
            backend_impl = HTTPMemoryBackend(host="localhost", port=6000)
        else:
             raise FatalError(f"Unsupported MEMORY_BACKEND: {conf.memory_backend}")

        writer = Writer(backend_impl)
        
        # --- Transport Injection (Stage 5 Isolation) ---
        # 1. Create Adapter using Factory (Stage 5)
        t_config = {
            'host': conf.bus_host,
            'port': conf.bus_port,
            'brokers': conf.bus_host,
            'client_id': f"ingest-{conf.stream_id}"
        }
        
        transport_adapter = TransportFactory.create_producer(conf.transport_type, t_config)
        transport_adapter.start()
        
        # 2. Inject into Core Logic
        publisher = StreamPublisher(conf, transport_adapter)

        heartbeat = Heartbeat(conf.stream_id)
        
        rtsp.connect()

    except FatalError as e:
        print(f"FATAL: Startup Failed - {e.message}")
        sys.exit(1)

    print(f">>> Ingestion Running | Stream: {conf.stream_id} | Transport: {conf.transport_type} <<<")

    while runtime.should_continue():
        try:
            heartbeat.tick()
            packet = reader.next_packet()
            if packet is None: 
                # If EOF (video file ended), we might want to loop or exit.
                # For streaming service, usually we wait/retry.
                # Here we loop logic safe.
                time.sleep(0.1)
                continue 

            if packet.pts <= 0:
                metrics.inc_dropped_pts(); continue

            raw_frame = decoder.decode(packet)
            if raw_frame is None:
                metrics.inc_dropped_corrupt(); continue
            
            metrics.inc_captured()

            if not selector.allow(packet.pts):
                metrics.inc_dropped_fps(); continue

            clean_frame = normalizer.process(raw_frame)
            fingerprint = anchor.generate(clean_frame)
            identity = FrameIdentity(conf.stream_id, packet.pts, fingerprint)

            ref = writer.write(clean_frame, identity)
            
            # Logic Layer Call
            publisher.publish(identity, packet.timestamp, ref)
            
            metrics.inc_processed()
        
        except FatalError as e:
            print(f"!!! FATAL ERROR !!! {e.message}"); break
        except Exception as e:
            print(f"!!! CRASH !!! {str(e)}"); break

    transport_adapter.stop()
    rtsp.close()
    runtime.shutdown()
    sys.exit(0)

if __name__ == "__main__":
    main()