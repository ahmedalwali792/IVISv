import warnings

import pytest

from ivis.common.contracts.validators import validate_frame_contract_v1, ContractValidationError


def base_contract():
    return {
        "contract_version": 1,
        "frame_id": "f1",
        "stream_id": "s1",
        "camera_id": "c1",
        "pts": 0.0,
        "timestamp_ms": 1000,
        "mono_ms": 2000,
        "memory": {"backend": "shm", "key": "1", "size": 640 * 480 * 3, "generation": 1},
        "frame_width": 640,
        "frame_height": 480,
        "frame_channels": 3,
        "frame_dtype": "uint8",
        "frame_color_space": "bgr",
    }


def test_missing_memory_field_triggers_error():
    c = base_contract()
    del c["memory"]["key"]
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "missing_memory_field"


def test_wrong_dtype_triggers_error():
    c = base_contract()
    c["frame_dtype"] = "float32"
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "unsupported_dtype"


def test_size_mismatch_triggers_error():
    c = base_contract()
    c["memory"]["size"] = 12345
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "memory_size_mismatch"


def test_missing_frame_id_triggers_error():
    c = base_contract()
    del c["frame_id"]
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "bad_frame_id"


def test_missing_timestamp_ms_triggers_error():
    c = base_contract()
    del c["timestamp_ms"]
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "bad_timestamp_ms"


def test_wrong_timestamp_ms_type_triggers_error():
    c = base_contract()
    c["timestamp_ms"] = "1000"
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "bad_timestamp_ms"


def test_wrong_mono_ms_type_triggers_error():
    c = base_contract()
    c["mono_ms"] = "2000"
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "bad_mono_ms"


@pytest.mark.parametrize("legacy_value", ["1", "v1", "V1"])
def test_contract_version_normalizes_legacy_strings(legacy_value):
    c = base_contract()
    c["contract_version"] = legacy_value
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        validate_frame_contract_v1(c)
    assert c["contract_version"] == 1
    assert any(item.category is DeprecationWarning for item in caught)


@pytest.mark.parametrize("bad_value", ["v2", 2, 0, None])
def test_contract_version_rejects_invalid_values(bad_value):
    c = base_contract()
    c["contract_version"] = bad_value
    with pytest.raises(ContractValidationError) as exc:
        validate_frame_contract_v1(c)
    assert exc.value.reason_code == "contract_version_mismatch"
