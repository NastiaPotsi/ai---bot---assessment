import pytest

from app.models.session import ConversationStep, SessionStatus


@pytest.mark.asyncio
async def test_workflow_collects_request_then_identity_and_completes(app_container):
    session = await app_container.session_service.create_session(
        app_container.prompt_config.required_request_fields
    )

    first = await app_container.workflow.run(
        session["session_id"],
        "I need access-grant to production because this is required for urgent incident support.",
    )

    assert first["status"] == SessionStatus.ACTIVE.value
    assert first["current_step"] == ConversationStep.COLLECT_IDENTITY_DETAILS.value
    assert "full name" in first["assistant_response"]
    assert "employee" not in first["assistant_response"]

    second = await app_container.workflow.run(
        session["session_id"],
        "My name is John Doe.",
    )

    assert second["status"] == SessionStatus.ACTIVE.value
    assert second["current_step"] == ConversationStep.COLLECT_IDENTITY_DETAILS.value
    assert "employee" in second["assistant_response"]

    third = await app_container.workflow.run(
        session["session_id"],
        "1234",
    )

    assert third["status"] == SessionStatus.COMPLETED.value
    assert third["current_step"] == ConversationStep.COMPLETED.value
    assert "submitted" in third["assistant_response"]

    stored_requests = await app_container.request_collection.all_documents()
    assert len(stored_requests) == 1
    assert stored_requests[0]["prompt_version"] == "v1"
    assert stored_requests[0]["request_data"]["request_type"] == "access-grant"
    assert "requester_name" not in stored_requests[0]["request_data"]
    assert "employee_id" not in stored_requests[0]["request_data"]
