
import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Adjust path to include project root
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from detection.ingest.consumer import ZmqFrameConsumer
from detection.postprocess.parse import parse_output

class TestRegression(unittest.TestCase):
    def test_zmq_consumer_connect_idempotent(self):
        """Test that ZmqFrameConsumer.connect() is idempotent."""
        consumer = ZmqFrameConsumer(endpoint="tcp://localhost:5555")
        consumer.zmq = MagicMock()
        mock_ctx = MagicMock()
        consumer.zmq.Context.instance.return_value = mock_ctx
        mock_socket = MagicMock()
        mock_ctx.socket.return_value = mock_socket

        # First connect
        consumer.connect()
        mock_socket.connect.assert_called_once_with("tcp://localhost:5555")
        
        # Second connect
        consumer.connect()
        # Should still be called only once
        mock_socket.connect.assert_called_once_with("tcp://localhost:5555")
        
        print("\n[PASS] test_zmq_consumer_connect_idempotent")

    def test_track_id_one_to_one_matching(self):
        """Test global one-to-one matching for track_id assignment."""
        # Setup: 2 tracks, 2 detections.
        # Track 0 (ID 100) overlaps Det 0 (IoU 0.9) and Det 1 (IoU 0.5)
        # Track 1 (ID 101) overlaps Det 1 (IoU 0.9)
        # Old greedy logic might assign Track 0 to Det 1 if processed first? 
        # Actually greedy logic usually assigns best IoU first if sorted? 
        # Or simple iteration: for det in dets: find best track.
        # If Det 1 comes first, it sees Track 0 (0.5) and Track 1 (0.9). Picks Track 1.
        # If Det 0 comes next, it sees Track 0 (0.9). Picks Track 0.
        # Result: T1->D1, T0->D0. Correct.
        
        # Let's try ambiguous case:
        # T0 (ID 100) overlaps D0 (0.4)
        # T1 (ID 101) overlaps D0 (0.5 - better)
        # D1 overlaps T1 (0.9 - best for T1)
        # Greedy per detection (D0 then D1):
        # D0 looks at T0(0.4), T1(0.5). Picks T1.
        # D1 looks at T1(0.9) -> T1 ALREADY USED (if flag set).
        # If logic is: "for det... unused.discard(best_idx)".
        # D0 picks T1. D1 finds T1 used. D1 gets NOTHING (or T0 if overlaps).
        # Global optimal: D1-T1 (0.9) is strongest match. D0 should get T0 (0.4).
        
        frame_contract = {
            "frame_id": "f1", "stream_id": "s1", "camera_id": "c1", 
            "timestamp_ms": 1000, "mono_ms": 1000, "memory": "shm://1"
        }
        
        # BBox format: [x1, y1, x2, y2]
        # D0: [0, 0, 100, 100]
        # D1: [100, 0, 200, 100]
        
        # T0: [0, 0, 100, 100] (IoU 1.0 with D0)
        # T1: [100, 0, 200, 100] (IoU 1.0 with D1)
        # Let's make it tricky.
        
        # Case: D0 overlaps T0(0.4) and T1(0.6)
        #       D1 overlaps T1(0.9)
        # Expectation: T1 matches D1 (0.9 > 0.6). T0 matches D0.
        
        # D0: [0,0, 100,100] Area 10000
        # T0: [0,0, 60, 60] Area 3600. Intersection [0,0,60,60]=3600. IoU = 3600 / (10000+3600-3600) = 0.36
        
        # Let's just mock exact IoU logic behavior by using non-overlapping boxes in space 
        # but overlapping logic? No, must be real geometry.
        
        raw_results = {
            "timing": {},
            "detections": [
                [[0,0,100,100], 0.9, 1], # D0
                [[200,0,300,100], 0.9, 1], # D1
            ],
            "tracks": []
        }
        
        # We need specific overlaps.
        # T0 overlaps D0 (0.4), T1 overlaps D0 (0.5), T1 overlaps D1 (0.9)
        # Impossible geometry? 
        # Only if T1 covers D0 and D1? BBox can be large.
        
        # Let's use simple logic check:
        # D0 is a small box inside T1.
        # D1 is the main match for T1.
        
        # T1: [0,0, 300,100] (Large box covering D0 and D1)
        # D0: [10,10, 50,50] (Inside T1)
        # D1: [200,10, 290,90] (Inside T1, better fit?)
        # Let's just create raw tracks.
        
        # We will trust the implementation to use IoU.
        # Let's use exact coordinates.
        
        # D0 at 10,10, 20,20. 10x10=100.
        # D1 at 30,10, 40,20. 10x10=100.
        
        # T0 overlaps D0 perfectly. [10,10,20,20]. ID=100.
        # T1 overlaps D0 perfectly also? No duplicate tracks usually.
        
        # Scenario from prompt: "One-to-one... IoU-based but globally consistent"
        # D0 overlaps T0 (0.8). D1 overlaps T0 (0.9).
        # Greedy D0 first: Picks T0. D1 gets nothing.
        # Global: D1 picks T0 (0.9 > 0.8). D0 gets nothing.
        
        raw_results["detections"] = [
            [[10,10,20,20], 0.9, 1], # D0
            [[11,11,21,21], 0.9, 1], # D1 (Shifted by 1, matches T0 very well)
        ]
        
        # T0 matches D1 better than D0?
        # T0: [11,11,21,21]. IoU(D1, T0) = 1.0. IoU(D0, T0) > 0.
        # D0 [10,10,20,20] vs T0 [11,11,21,21]. Inter [11,11,20,20] (9x9=81). Union 100+100-81 = 119. IoU=0.68.
        
        raw_results["tracks"] = [
            {"bbox": [11,11,4,4], "bbox_xyxy": [11,11,21,21], "track_id": 999} 
        ]
        
        # Greedy loop (D0 then D1):
        # D0 sees T0 (IoU 0.68). Matches! T0 used.
        # D1 sees T0 (IoU 1.0). T0 already used. D1 gets nothing.
        
        # Global matching:
        # Pairs: (D1,T0, 1.0), (D0,T0, 0.68).
        # Sort -> D1,T0 first. Assigned.
        # D0,T0 -> T0 used. Skipped.
        # Result: D1 has track_id 999. D0 has None.
        
        res = parse_output(frame_contract, raw_results)
        dets = res["detections"]
        
        # Verify D1 got the track
        d0 = dets[0] # [10,10,20,20]
        d1 = dets[1] # [11,11,21,21]
        
        self.assertNotIn("track_id", d0, "D0 should not get track_id (was stolen by better match D1)")
        self.assertEqual(d1.get("track_id"), 999, "D1 should get track_id 999")
        
        print("\n[PASS] test_track_id_one_to_one_matching")

if __name__ == "__main__":
    unittest.main()
