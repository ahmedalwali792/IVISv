# [2025-12-29] results/main.py
import sys
import os
from results.config import Config
from results.ingest.consumer import ResultConsumer
from results.sinks.jsonl import JsonlSink
from results.sinks.dashboard import DashboardSink

try:
    from infrastructure.transport.factory import TransportFactory
except ImportError:
    print("FATAL: Infrastructure missing")
    sys.exit(1)

def main():
    print(">>> Result Plane: Stage 0.9.2 / Stage 5 Compliant <<<")
    config = Config()
    
    sinks = [
        JsonlSink(config.log_file),
        DashboardSink(config.canvas_width, config.canvas_height)
    ]
    
    # Init Transport (Stage 5 Factory)
    t_config = {
        'host': config.bus_host,
        'port': config.bus_port,
        'topic': config.output_topic,
        'brokers': config.bus_host,
        'group_id': 'results-svc-v1'
    }

    transport = TransportFactory.create_consumer(config.transport_type, t_config)
    transport.start()
    
    # Inject
    consumer = ResultConsumer(transport)
    
    try:
        print(f">>> Result Loop Running | Transport: {config.transport_type} <<<")
        for res in consumer:
            print(f"[RESULT] {res.get('frame_id')[:8]}")
            for s in sinks: s.handle(res)
    except KeyboardInterrupt:
        transport.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()