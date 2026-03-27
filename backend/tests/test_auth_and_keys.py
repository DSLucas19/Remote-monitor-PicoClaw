def login(client, api_key: str) -> str:
    response = client.post("/api/auth/session", json={"api_key": api_key})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_auth_and_key_revoke_flow(client):
    admin_token = login(client, "test-initial-key")

    create_response = client.post(
        "/api/keys",
        json={"name": "Machine B"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_response.status_code == 201, create_response.text
    payload = create_response.json()
    plain_key = payload["api_key"]
    key_id = payload["id"]

    new_key_token = login(client, plain_key)
    assert new_key_token

    revoke_response = client.post(
        f"/api/keys/{key_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke_response.status_code == 200, revoke_response.text

    relogin = client.post("/api/auth/session", json={"api_key": plain_key})
    assert relogin.status_code == 401


def test_logs_websocket_requires_valid_session(client):
    token = login(client, "test-initial-key")
    client.app.state.log_broker.publish("metaclaw", "system", "hello", source="system")

    with client.websocket_connect(f"/ws/logs?token={token}&limit=10") as websocket:
        found = False
        for _ in range(10):
            message = websocket.receive_json()
            if message["message"] == "hello":
                found = True
                break
        assert found
