"""
Agent registration API tests.

Each test runs in an independent in-memory SQLite session.
"""

import pytest


# ---------------------------------------------------------------------------
# POST /agents/register
# ---------------------------------------------------------------------------


def test_register_agent_success(client):
    """A valid payload registers an agent successfully."""
    payload = {
        "name": "TestAgent",
        "description": "An agent that specializes in code generation",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "agent_id" in data
    assert data["name"] == "TestAgent"
    assert data["description"] == "An agent that specializes in code generation"
    assert data["wallet_address"] == "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX"
    assert data["endpoint"] == "https://example.com/agent"
    assert data["trust_score"] == 0.5
    assert "created_at" in data


def test_register_agent_duplicate_name(client):
    """Registering an agent with a duplicate name returns 409 Conflict."""
    payload = {
        "name": "DuplicateAgent",
        "description": "Test agent",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    client.post("/agents/register", json=payload)
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 409


def test_register_agent_invalid_wallet(client):
    """An empty wallet_address returns 422."""
    payload = {
        "name": "AgentWithEmptyWallet",
        "description": "Test agent",
        "wallet_address": "",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_whitespace_wallet(client):
    """A whitespace-only wallet_address returns 422."""
    payload = {
        "name": "AgentWithWhitespaceWallet",
        "description": "Test agent",
        "wallet_address": "   ",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_invalid_endpoint(client):
    """A non-URL endpoint returns 422."""
    payload = {
        "name": "AgentWithBadEndpoint",
        "description": "Test agent",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "not-a-url",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_missing_fields(client):
    """Missing required fields returns 422."""
    payload = {
        "name": "IncompleteAgent",
        # description, wallet_address, endpoint are missing
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_invalid_wallet_bad_chars(client):
    """A wallet_address containing invalid Base58 characters (0, O, I, l) returns 422."""
    payload = {
        "name": "AgentBadCharsWallet",
        "description": "Test agent",
        "wallet_address": "0OIlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # invalid chars
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_wallet_too_short(client):
    """A wallet_address shorter than 32 characters returns 422."""
    payload = {
        "name": "AgentShortWallet",
        "description": "Test agent",
        "wallet_address": "So1anaWa11etXXXXXXXXXXXXXXXXXXX",  # 31 chars
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_name_too_long(client):
    """A name longer than 100 characters returns 422."""
    payload = {
        "name": "A" * 101,
        "description": "Test agent",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_description_too_long(client):
    """A description longer than 500 characters returns 422."""
    payload = {
        "name": "AgentLongDesc",
        "description": "A" * 501,
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_empty_description(client):
    """An empty description returns 422."""
    payload = {
        "name": "AgentEmptyDesc",
        "description": "",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 422


def test_register_agent_name_at_max_length(client):
    """A name of exactly 100 characters succeeds."""
    payload = {
        "name": "A" * 100,
        "description": "Boundary value test",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXXXXXXXXXXX",
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 201


def test_register_agent_wallet_at_min_length(client):
    """A wallet_address of exactly 32 characters succeeds."""
    payload = {
        "name": "AgentMinWallet",
        "description": "Boundary value test",
        "wallet_address": "So1anaWa11etAddressXXXXXXXXXXXXXX",  # 32 chars
        "endpoint": "https://example.com/agent",
    }
    response = client.post("/agents/register", json=payload)

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /agents
# ---------------------------------------------------------------------------


def test_list_agents_empty(client):
    """Returns an empty array when no agents are registered."""
    response = client.get("/agents")

    assert response.status_code == 200
    assert response.json() == []


def test_list_agents_multiple(client):
    """Returns all registered agents when multiple exist."""
    agents = [
        {
            "name": "AgentAlpha",
            "description": "Specialty A",
            "wallet_address": "Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "endpoint": "https://alpha.example.com/agent",
        },
        {
            "name": "AgentBeta",
            "description": "Specialty B",
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
    """Returns the correct agent info for an existing agent_id."""
    payload = {
        "name": "RetrievableAgent",
        "description": "Test for retrieval",
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
    """Returns 404 for a non-existent agent_id."""
    response = client.get("/agents/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
