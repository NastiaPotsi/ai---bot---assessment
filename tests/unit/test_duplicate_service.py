import pytest


@pytest.mark.asyncio
async def test_duplicate_detection_finds_completed_request(app_container):
    duplicate_key = app_container.duplicate_service.create_key("John Doe", "1234")
    created = await app_container.request_service.create_request(
        session_id="session-1",
        prompt_version="v1",
        request_data={
            "request_type": "access-grant",
            "target_environment": "production",
            "justification": "Needed for support.",
        },
        duplicate_key=duplicate_key,
    )

    computed_key, duplicate = await app_container.duplicate_service.find_duplicate(
        " john  doe ",
        "1234",
    )

    assert computed_key == duplicate_key
    assert duplicate is not None
    assert duplicate["request_id"] == created["request_id"]

