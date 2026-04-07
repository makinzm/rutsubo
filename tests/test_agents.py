"""
エージェント登録 API のテスト。

各テストは独立したインメモリ SQLite セッションで実行される。
"""

import pytest


# ---------------------------------------------------------------------------
# POST /agents/register
# ---------------------------------------------------------------------------


def test_register_agent_success(client):
    """正常なデータでエージェントを登録できる。"""
    payload = {
        "name": "TestAgent",
        "description": "コード生成が得意なエージェント",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data
    assert data["name"] == "TestAgent"
    assert data["description"] == "コード生成が得意なエージェント"
    assert data["wallet_address"] == "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX"
    assert data["endpoint"] == "https://example.com/agent"
    assert data["trust_score"] == 0.5
    assert "created_at" in data


def test_register_agent_duplicate_name(client):
    """同じ名前で二重登録すると 409 Conflict を返す。"""
    payload = {
        "name": "DuplicateAgent",
        "description": "テスト用エージェント",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    client.post("/agents/register", json=payload)
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 409


def test_register_agent_invalid_wallet(client):
    """wallet_address が空文字の場合は 422 を返す。"""
    payload = {
        "name": "AgentWithEmptyWallet",
        "description": "テスト用",
        "wallet_address": "",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_whitespace_wallet(client):
    """wallet_address が空白のみの場合は 422 を返す。"""
    payload = {
        "name": "AgentWithWhitespaceWallet",
        "description": "テスト用",
        "wallet_address": "   ",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_invalid_endpoint(client):
    """endpoint が URL 形式でない場合は 422 を返す。"""
    payload = {
        "name": "AgentWithBadEndpoint",
        "description": "テスト用",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "not-a-url",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_missing_fields(client):
    """必須フィールドが欠落している場合は 422 を返す。"""
    payload = {
        "name": "IncompleteAgent",
        # description, wallet_address, endpoint が欠落
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_invalid_wallet_bad_chars(client):
    """Base58 として無効な文字（0, O, I, l）を含む wallet_address は 422 を返す。"""
    payload = {
        "name": "AgentBadCharsWallet",
        "description": "テスト用",
        "wallet_address": "0OIlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 無効文字含む
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_wallet_too_short(client):
    """wallet_address が32文字未満の場合は 422 を返す。"""
    payload = {
        "name": "AgentShortWallet",
        "description": "テスト用",
        "wallet_address": "So1anaWa11etXXXXXXXXXXXXXXXXXXX",  # 31文字
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_name_too_long(client):
    """name が100文字を超える場合は 422 を返す。"""
    payload = {
        "name": "A" * 101,
        "description": "テスト用",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_description_too_long(client):
    """description が500文字を超える場合は 422 を返す。"""
    payload = {
        "name": "AgentLongDesc",
        "description": "A" * 501,
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_empty_description(client):
    """description が空文字の場合は 422 を返す。"""
    payload = {
        "name": "AgentEmptyDesc",
        "description": "",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_name_at_max_length(client):
    """name がちょうど100文字の場合は成功する。"""
    payload = {
        "name": "A" * 100,
        "description": "境界値テスト用",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 201


def test_register_agent_wallet_at_min_length(client):
    """wallet_address がちょうど32文字の場合は成功する。"""
    payload = {
        "name": "AgentMinWallet",
        "description": "境界値テスト用",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXX",  # 32文字
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /agents
# ---------------------------------------------------------------------------


def test_list_agents_empty(client):
    """エージェントが 0 件のとき、空配列を返す。"""
    response = client.get("/agents")

    assert response.status_code == 200
    assert response.json() == []


def test_list_agents_multiple(client):
    """複数エージェント登録後、全件を返す。"""
    agents = [
        {
            "name": "AgentAlpha",
            "description": "専門A",
            "wallet_address": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "endpoint": "https://alpha.example.com/agent",
        },
        {
            "name": "AgentBeta",
            "description": "専門B",
            "wallet_address": "Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "endpoint": "https://beta.example.com/agent",
        },
    ]
    for a in agents:
        client.post("/agents/register", json=a)

    response = client.get("/agents")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {a["name"] for a in data}
    assert names == {"AgentAlpha", "AgentBeta"}


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}
# ---------------------------------------------------------------------------


def test_get_agent_success(client):
    """存在する agent_id で取得すると、正しいエージェント情報を返す。"""
    payload = {
        "name": "RetrievableAgent",
        "description": "取得テスト用",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    created = client.post("/agents/register", json=payload).json()
    agent_id = created["agent_id"]

    response = client.get(f"/agents/{agent_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == agent_id
    assert data["name"] == "RetrievableAgent"


def test_get_agent_not_found(client):
    """存在しない agent_id で取得すると 404 を返す。"""
    response = client.get("/agents/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
