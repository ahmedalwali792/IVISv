# FILE: detection/preprocess/validate.py
# ------------------------------------------------------------------------------
from detection.errors.fatal import NonFatalError
from ivis.common.contracts.validators import ContractValidationError, validate_frame_contract_v1


def validate_frame(contract: dict):
    """Compatibility wrapper around the official contract validator."""
    try:
        validate_frame_contract_v1(contract)
    except ContractValidationError as exc:
        raise NonFatalError(f"Contract Violation: {exc.message}") from exc
