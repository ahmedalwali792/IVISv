import multiprocessing
import time
import os
import sys
import numpy as np
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from memory.shm_ring import ShmRing

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("stress_test")

SLOT_SIZE = 1024 * 1024  # 1 MB
SLOT_COUNT = 10
SHM_NAME = "stress_test_shm"
SHM_META = "stress_test_meta"
DURATION = 5  # seconds

def writer_process(stop_event):
    ring = ShmRing(SHM_NAME, SHM_META, SLOT_SIZE, SLOT_COUNT, create=True, recreate_on_mismatch=True)
    counter = 0
    # Create a pattern we can verify: Fill buffer with a single byte value that increments
    try:
        while not stop_event.is_set():
            val = counter % 255
            # Create a 1MB buffer filled with 'val'
            data = bytes([val]) * SLOT_SIZE
            ring.write(data)
            counter += 1
            if counter % 100 == 0:
                time.sleep(0.001) # Slight pause to let reader catch up occasionally
    except Exception as e:
        logger.error(f"Writer failed: {e}")
    finally:
        ring.close()

def reader_process(stop_event, error_queue):
    # giving writer a moment to start
    time.sleep(0.5)
    try:
        ring = ShmRing(SHM_NAME, SHM_META, SLOT_SIZE, SLOT_COUNT, create=False)
    except FileNotFoundError:
        logger.error("Reader could not find SHM")
        error_queue.put("SHM not found")
        return

    reads = 0
    torn_reads = 0
    
    try:
        while not stop_event.is_set():
            # Use read_latest
            data, idx, gen = ring.read_latest()
            if data is None:
                continue
                
            reads += 1
            # Verify data integrity
            # We expect all bytes to be the same
            first_byte = data[0]
            # Fast check using numpy or just list slicing if simple
            # Since we used bytes([val]) * size, every byte must be 'first_byte'
            # Check the last byte and middle byte to be sure
            if data[-1] != first_byte or data[len(data)//2] != first_byte:
                logger.error(f"TORN READ DETECTED! Gen={gen}, Index={idx}")
                torn_reads += 1
                error_queue.put(f"Torn read at gen {gen}")
            
            # Additional check: convert to numpy to check all? (Expensive but accurate)
            # arr = np.frombuffer(data, dtype=np.uint8)
            # if not np.all(arr == first_byte):
            #    logger.error("Numpy check mismatch")
            
    except Exception as e:
        logger.error(f"Reader failed: {e}")
        error_queue.put(str(e))
    finally:
        ring.close()
        logger.info(f"Reader finished. Total reads: {reads}, Torn reads: {torn_reads}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    logger.info("Starting SHM Stress Test...")
    
    stop_event = multiprocessing.Event()
    error_queue = multiprocessing.Queue()
    
    p_writer = multiprocessing.Process(target=writer_process, args=(stop_event,))
    p_reader = multiprocessing.Process(target=reader_process, args=(stop_event, error_queue))
    
    p_writer.start()
    p_reader.start()
    
    time.sleep(DURATION)
    stop_event.set()
    
    p_writer.join()
    p_reader.join()
    
    errors = []
    while not error_queue.empty():
        errors.append(error_queue.get())
        
    if errors:
        logger.error(f"Test FAILED with {len(errors)} errors:")
        for e in errors:
            logger.error(f" - {e}")
        sys.exit(1)
    else:
        logger.info("Test PASSED: No torn reads detected.")
