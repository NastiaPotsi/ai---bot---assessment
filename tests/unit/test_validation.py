from app.services.validators import validate_identity_details, validate_request_details


def test_request_validation_preserves_partial_data(prompt_config):
    existing = {"request_type": "access-grant"}
    extracted = {
        "target_environment": "production",
        "justification": "Needed for urgent incident support.",
    }

    result = validate_request_details(extracted, existing, prompt_config)

    assert result.valid
    assert result.data == {
        "request_type": "access-grant",
        "target_environment": "production",
        "justification": "Needed for urgent incident support.",
    }
    assert result.missing_fields == []


def test_request_validation_rejects_invalid_allowed_value(prompt_config):
    result = validate_request_details(
        {
            "request_type": "laptop-request",
            "target_environment": "production",
            "justification": "Needed for a release.",
        },
        {},
        prompt_config,
    )

    assert not result.valid
    assert "request_type" in result.missing_fields
    assert result.errors


def test_identity_validation_accepts_name_and_employee_id(prompt_config):
    result = validate_identity_details(
        {"requester_name": "John Doe", "employee_id": "1234"},
        prompt_config,
    )

    assert result.valid
    assert result.data["requester_name"] == "John Doe"
    assert result.data["employee_id"] == "1234"


def test_identity_validation_preserves_partial_data(prompt_config):
    result = validate_identity_details(
        {"employee_id": "1234"},
        prompt_config,
        {"requester_name": "John Doe"},
    )

    assert result.valid
    assert result.data == {
        "requester_name": "John Doe",
        "employee_id": "1234",
    }


def test_identity_validation_rejects_bad_employee_id(prompt_config):
    result = validate_identity_details(
        {"requester_name": "John Doe", "employee_id": "1234!"},
        prompt_config,
    )

    assert not result.valid
    assert "employee_id" in result.missing_fields
    assert result.errors
