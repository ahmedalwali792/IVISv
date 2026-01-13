"""Result contract v1 schema and validator.
"""
import warnings
from typing import Any, Dict, List

from ivis.common.contracts.validators import ContractValidationError


def _is_number(x):
    return isinstance(x, (int, float))


def validate_result_contract_v1(result: Dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise ContractValidationError("not_a_dict", "result must be a dict")

    cv = result.get("contract_version")
    if isinstance(cv, bool):
        cv = None
    warning_msg = None
    if isinstance(cv, str):
        normalized = cv.strip()
        if normalized.lower() == "v1":
            warning_msg = "result contract_version 'v1' is deprecated; use int 1"
            cv = 1
        elif normalized == "1":
            warning_msg = "result contract_version '1' (string) is deprecated; use int 1"
            cv = 1
    if cv != 1:
        raise ContractValidationError("contract_version_mismatch", "unsupported result contract_version")
    if warning_msg:
        warnings.warn(warning_msg, DeprecationWarning, stacklevel=2)
    if result.get("contract_version") != 1:
        result["contract_version"] = 1

    for field in ("frame_id", "stream_id", "camera_id"):
        if field not in result or not isinstance(result.get(field), str):
            raise ContractValidationError("missing_id_field", f"{field} must be a non-empty string")

    if "timestamp_ms" not in result or not isinstance(result.get("timestamp_ms"), int):
        raise ContractValidationError("bad_timestamp_ms", "timestamp_ms must be int (ms)")
    if "mono_ms" not in result or not isinstance(result.get("mono_ms"), int):
        raise ContractValidationError("bad_mono_ms", "mono_ms must be int (ms)")

    # detections
    dets = result.get("detections")
    if dets is None:
        raise ContractValidationError("missing_detections", "detections must be present as a list")
    if not isinstance(dets, list):
        raise ContractValidationError("bad_detections", "detections must be a list")
    for i, d in enumerate(dets):
        if not isinstance(d, dict):
            raise ContractValidationError("bad_detection_entry", f"detection[{i}] must be a dict")
        bbox = d.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or not all(_is_number(v) for v in bbox):
            raise ContractValidationError("bad_bbox", f"detection[{i}].bbox must be [x1,y1,x2,y2]")
        conf = d.get("conf")
        if not _is_number(conf) or conf < 0 or conf > 1:
            raise ContractValidationError("bad_confidence", f"detection[{i}].conf must be 0..1")
        if "class_id" not in d:
            raise ContractValidationError("missing_class_id", f"detection[{i}] missing class_id")

    # model sub-schema
    model = result.get("model")
    if not isinstance(model, dict):
        raise ContractValidationError("missing_model", "model metadata must be present")
    if not model.get("name") or not isinstance(model.get("name"), str):
        raise ContractValidationError("bad_model_name", "model.name must be a non-empty string")
    if not model.get("version"):
        # allow empty version but require field presence
        model["version"] = str(model.get("version", ""))
    if "threshold" in model and not _is_number(model.get("threshold")):
        raise ContractValidationError("bad_model_threshold", "model.threshold must be numeric")
    if "input_size" in model:
        ins = model.get("input_size")
        if not isinstance(ins, (list, tuple)) or len(ins) not in (2, 3):
            raise ContractValidationError("bad_model_input_size", "model.input_size must be [h,w] or [h,w,c]")

    # timing
    timing = result.get("timing")
    if timing is None or not isinstance(timing, dict):
        raise ContractValidationError("missing_timing", "timing must be present")
    if "inference_ms" not in timing or not _is_number(timing.get("inference_ms")):
        raise ContractValidationError("bad_timing", "timing.inference_ms must be present and numeric")

    return None
