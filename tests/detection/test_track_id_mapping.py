from detection.postprocess.parse import parse_output


def test_track_id_association_tolerates_float_jitter():
    frame_contract = {
        "contract_version": 1,
        "frame_id": "f1",
        "stream_id": "s1",
        "camera_id": "c1",
        "timestamp_ms": 1000,
        "mono_ms": 2000,
        "pts": 0.0,
    }
    raw_results = {
        "detections": [([10.0, 20.0, 50.0, 60.0], 0.9, 1)],
        "tracks": [
            {
                "track_id": 42,
                "bbox_xyxy": [10.15, 19.85, 50.05, 60.1],
            }
        ],
        "timing": {"inference_ms": 1.0},
    }

    result = parse_output(frame_contract, raw_results)
    assert result["detections"][0]["track_id"] == 42
