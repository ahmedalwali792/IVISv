# [2025-12-29] detection/main.py
import sys
import os
from detection.config import Config
from detection.ingest.consumer import FrameConsumer
from detection.memory.reader import MemoryReader
from detection.frame.decoder import FrameDecoder
from detection.preprocess.validate import validate_frame
from detection.preprocess.tensorize import to_model_input
from detection.model.loader import load_model
from detection.model.runner import ModelRunner
from detection.postprocess.parse import parse_output
from detection.publish.results import ResultPublisher
from detection.errors.fatal import FatalError, NonFatalError
from detection.metrics.counters import metrics
from detection.runtime import Runtime

# Import Transport Factory (Stage 5)
try:
    from infrastructure.transport.factory import TransportFactory
    TRANSPORT_AVAILABLE = True
except ImportError:
    print("FATAL: Infrastructure missing")
    sys.exit(1)

def main():
    print(">>> Detection Service: Stage 0.9.2 (Isolated) / Stage 5 Compliant <<<")
    runtime = Runtime()

    try:
        # 1. Init Core Components
        model = load_model()
        runner = ModelRunner(model)
        
        # 2. Init Transport Adapters (Using Factory)
        t_conf_consumer = {
            'host': Config.BUS_HOST, 
            'port': Config.BUS_PORT, 
            'topic': Config.INPUT_TOPIC,
            'brokers': Config.BUS_HOST,
            'group_id': 'detection-svc-v1'
        }
        
        t_conf_producer = {
            'host': Config.BUS_HOST, 
            'port': Config.BUS_PORT,
            'brokers': Config.BUS_HOST,
            'client_id': 'detection-svc-producer'
        }

        transport_consumer = TransportFactory.create_consumer(Config.TRANSPORT_TYPE, t_conf_consumer)
        transport_consumer.start()
        
        transport_producer = TransportFactory.create_producer(Config.TRANSPORT_TYPE, t_conf_producer)
        transport_producer.start()

        # 3. Inject into Logic
        consumer = FrameConsumer(transport_consumer) # Logic wraps Adapter
        publisher = ResultPublisher(transport_producer) # Logic wraps Adapter
        reader = MemoryReader()
        decoder = FrameDecoder()

        print(f">>> Detection Loop Running | Transport: {Config.TRANSPORT_TYPE} <<<")

        for frame_contract in consumer:
            if not runtime.running: break
            metrics.inc_received()

            try:
                validate_frame(frame_contract)
                raw_bytes = reader.read(frame_contract["memory"])
                frame = decoder.decode(raw_bytes)
                tensor = to_model_input(frame)
                raw_results = runner.infer(tensor)
                result = parse_output(frame_contract["frame_id"], raw_results)
                result["memory"] = frame_contract["memory"] # <--- إضافة هذا السطر
                publisher.publish(result)
                metrics.inc_processed()

            except NonFatalError as e:
                metrics.inc_dropped()
                continue
            except FatalError as e:
                raise e
            except Exception as e:
                raise FatalError(f"Unexpected: {e}")

    except FatalError as e:
        print(f"FATAL: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()