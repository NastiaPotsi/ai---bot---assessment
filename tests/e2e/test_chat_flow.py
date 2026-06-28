import pytest

from app.models.session import ConversationStep, SessionStatus


@pytest.mark.asyncio
async def test_full_conversation_and_privacy_safe_duplicate_detection(
    async_client,
    app_container,
):
    first_session_response = await async_client.post("/sessions")
    assert first_session_response.status_code == 201
    first_session_id = first_session_response.json()["session_id"]

    first_chat_response = await async_client.post(
        f"/chat/{first_session_id}",
        json={"message": "I need help with an engineering request."},
    )
    assert first_chat_response.status_code == 200
    first_chat = first_chat_response.json()
    assert first_chat["status"] == SessionStatus.ACTIVE.value
    assert first_chat["current_step"] == ConversationStep.COLLECT_REQUEST_DETAILS.value
    assert "What type" in first_chat["assistant_response"]
    assert "target environment" not in first_chat["assistant_response"]

    request_type_response = await async_client.post(
        f"/chat/{first_session_id}",
        json={"message": "access-grant"},
    )
    assert request_type_response.status_code == 200
    request_type_payload = request_type_response.json()
    assert request_type_payload["status"] == SessionStatus.ACTIVE.value
    assert request_type_payload["current_step"] == ConversationStep.COLLECT_REQUEST_DETAILS.value
    assert "target environment" in request_type_payload["assistant_response"]
    assert "justification" not in request_type_payload["assistant_response"]

    environment_response = await async_client.post(
        f"/chat/{first_session_id}",
        json={"message": "production"},
    )
    assert environment_response.status_code == 200
    environment_payload = environment_response.json()
    assert environment_payload["status"] == SessionStatus.ACTIVE.value
    assert environment_payload["current_step"] == ConversationStep.COLLECT_REQUEST_DETAILS.value
    assert "justification" in environment_payload["assistant_response"]

    justification_response = await async_client.post(
        f"/chat/{first_session_id}",
        json={"message": "justification is urgent incident support"},
    )
    assert justification_response.status_code == 200
    justification_payload = justification_response.json()
    assert justification_payload["status"] == SessionStatus.ACTIVE.value
    assert justification_payload["current_step"] == ConversationStep.COLLECT_IDENTITY_DETAILS.value
    assert "full name" in justification_payload["assistant_response"]
    assert "employee" not in justification_payload["assistant_response"]

    name_response = await async_client.post(
        f"/chat/{first_session_id}",
        json={"message": "My name is John Doe."},
    )
    assert name_response.status_code == 200
    name_payload = name_response.json()
    assert name_payload["status"] == SessionStatus.ACTIVE.value
    assert name_payload["current_step"] == ConversationStep.COLLECT_IDENTITY_DETAILS.value
    assert "employee" in name_payload["assistant_response"]

    name_debug_response = await async_client.get(f"/sessions/{first_session_id}")
    assert name_debug_response.status_code == 200
    assert "John Doe" not in name_debug_response.text

    completion_response = await async_client.post(
        f"/chat/{first_session_id}",
        json={"message": "1234"},
    )
    assert completion_response.status_code == 200
    completed = completion_response.json()
    assert completed["status"] == SessionStatus.COMPLETED.value
    assert "submitted" in completed["assistant_response"]

    debug_response = await async_client.get(f"/sessions/{first_session_id}")
    assert debug_response.status_code == 200
    debug_payload = debug_response.text
    assert "John Doe" not in debug_payload
    assert "1234" not in debug_payload
    assert "duplicate_key" not in debug_payload

    second_session_response = await async_client.post("/sessions")
    assert second_session_response.status_code == 201
    second_session_id = second_session_response.json()["session_id"]

    await async_client.post(
        f"/chat/{second_session_id}",
        json={
            "message": (
                "I need access-grant to production because this is required "
                "for urgent incident support."
            ),
        },
    )
    duplicate_name_response = await async_client.post(
        f"/chat/{second_session_id}",
        json={"message": "My name is John Doe."},
    )
    assert duplicate_name_response.status_code == 200
    assert "employee" in duplicate_name_response.json()["assistant_response"]

    duplicate_response = await async_client.post(
        f"/chat/{second_session_id}",
        json={"message": "1234"},
    )
    assert duplicate_response.status_code == 200
    duplicate_payload = duplicate_response.json()
    assert duplicate_payload["status"] == SessionStatus.AWAITING_DUPLICATE_CONFIRMATION.value
    assert duplicate_payload["current_step"] == ConversationStep.DUPLICATE_CONFIRMATION.value
    assert "possible existing request" in duplicate_payload["assistant_response"]
    assert "John Doe" not in duplicate_payload["assistant_response"]
    assert "1234" not in duplicate_payload["assistant_response"]

    duplicate_debug_response = await async_client.get(f"/sessions/{second_session_id}")
    assert duplicate_debug_response.status_code == 200
    duplicate_debug_payload = duplicate_debug_response.text
    assert "John Doe" not in duplicate_debug_payload
    assert "1234" not in duplicate_debug_payload
    assert "duplicate_key" not in duplicate_debug_payload

    update_response = await async_client.post(
        f"/chat/{second_session_id}",
        json={"message": "yes"},
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["status"] == SessionStatus.COMPLETED.value
    assert update_payload["current_step"] == ConversationStep.COMPLETED.value
    assert "updated" in update_payload["assistant_response"]
    assert "John Doe" not in update_payload["assistant_response"]
    assert "1234" not in update_payload["assistant_response"]

    stored_requests = await app_container.request_collection.all_documents()
    assert len(stored_requests) == 1
    assert stored_requests[0]["session_id"] == second_session_id
    assert stored_requests[0]["prompt_version"] == "v1"


@pytest.mark.asyncio
async def test_duplicate_declined_creates_new_request(async_client, app_container):
    """Declining the duplicate prompt creates a second, independent request."""

    async def _run_full_conversation(session_id: str) -> None:
        await async_client.post(
            f"/chat/{session_id}",
            json={
                "message": (
                    "I need access-grant to production because this is required "
                    "for urgent incident support."
                ),
            },
        )
        await async_client.post(
            f"/chat/{session_id}",
            json={"message": "My name is Jane Smith."},
        )
        await async_client.post(
            f"/chat/{session_id}",
            json={"message": "employee id is EMP999"},
        )

    first_session_id = (await async_client.post("/sessions")).json()["session_id"]
    await _run_full_conversation(first_session_id)

    first_stored = await app_container.request_collection.all_documents()
    assert len(first_stored) == 1
    assert first_stored[0]["status"] == "completed"

    second_session_id = (await async_client.post("/sessions")).json()["session_id"]
    await _run_full_conversation(second_session_id)

    duplicate_response = (
        await async_client.post(
            f"/chat/{second_session_id}",
            json={"message": "no"},
        )
    ).json()

    assert duplicate_response["status"] == SessionStatus.COMPLETED.value
    assert duplicate_response["current_step"] == ConversationStep.COMPLETED.value
    assert "submitted" in duplicate_response["assistant_response"]
    assert "Jane Smith" not in duplicate_response["assistant_response"]
    assert "EMP999" not in duplicate_response["assistant_response"]

    all_requests = await app_container.request_collection.all_documents()
    assert len(all_requests) == 2
    request_ids = {r["request_id"] for r in all_requests}
    assert len(request_ids) == 2
