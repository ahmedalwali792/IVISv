# FILE: detection/main.py
# ------------------------------------------------------------------------------
import sys
import os

from detection.metrics.counters import metrics
from detection.errors.fatal import FatalError, NonFatalError
from detection.frame.decoder import FrameDecoder
from detection.ingest.consumer import FrameConsumer
from detection.memory.reader import MemoryReader
from detection.model.loader import load_model
from detection.model.runner import ModelRunner
from detection.postprocess.parse import parse_output
from detection.preprocess.tensorize import to_model_input
from detection.preprocess.validate import validate_frame
from detection.publish.results import ResultPublisher
from detection.runtime import Runtime
from detection.metrics.counters import metrics

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print(">>> Detection Service: Stage 3 (Blind Consumer Frozen) <<<")
    runtime = Runtime()

    try:
        # 1. Initialization (Fatal if fails)
        model = load_model()
        runner = ModelRunner(model)
        runner.warmup()

        consumer = FrameConsumer()
        reader = MemoryReader()
        decoder = FrameDecoder()
        publisher = ResultPublisher()

        print(">>> Detection Loop Running <<<")

        # 2. Processing Loop
        for frame_contract in consumer:
            if not runtime.running:
                break

            metrics.inc_received()

            try:
                # A. Validate (Strict Clean Schema)
                validate_frame(frame_contract)
                
                # B. Read Raw Bytes (No reshape here)
                raw_bytes = reader.read(frame_contract["memory"])
                
                # C. Decode (Bytes -> Tensor) with Local Knowledge
                frame = decoder.decode(raw_bytes)

                # D. Inference
                tensor = to_model_input(frame)
                raw_results = runner.infer(tensor)
                
                # E. Publish
                result = parse_output(frame_contract["frame_id"], raw_results)
                publisher.publish(result)
                
                metrics.inc_processed()

            # === Stage 2: Error Discipline ===
            
            except NonFatalError as e:
                metrics.inc_dropped()
                continue

            except FatalError as e:
                metrics.fatal_crashes += 1
                print(f"!!! FATAL ERROR !!! {e.message} | Context: {e.context}")
                raise e

            except Exception as e:
                print(f"!!! UNHANDLED CRASH !!! {str(e)}")
                import traceback
                traceback.print_exc()
                raise FatalError(f"Unexpected: {e}")

    except FatalError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()