"""
reviewer サービスおよび agent_service.update_trust_score のテスト。

外部依存（Claude API）は unittest.mock でモックする。
DB は conftest.py の StaticPool インメモリ SQLite を使用。
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.agent import Agent


# ---------------------------------------------------------------------------
# テスト用 DB セットアップ（conftest.py と同じパターン）
# ---------------------------------------------------------------------------

_TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)


# ---------------------------------------------------------------------------
# test_reviewer_returns_score
# ---------------------------------------------------------------------------


def test_reviewer_returns_score():
    """Claude API をモックして evaluate_subtask が float スコアを返すことを確認する。"""
    from app.services.reviewer import evaluate_subtask

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text='{"score": 0.85}')]

    with patch("app.services.reviewer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_resp

        score = asyncio.run(
            evaluate_subtask(
                prompt="Pythonでfizzbuzzを実装してください",
                result="def fizzbuzz(n): ...",
                risk_level="medium",
            )
        )

    assert isinstance(score, float)
    assert score == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# test_reviewer_score_range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw_score,expected", [
    (0.0, 0.0),
    (1.0, 1.0),
    (0.5, 0.5),
    (-0.1, 0.0),   # 下限クランプ
    (1.5, 1.0),    # 上限クランプ
])
def test_reviewer_score_range(raw_score, expected):
    """Claude APIが返すスコアが0.0〜1.0の範囲にクランプされることを確認する。"""
    from app.services.reviewer import evaluate_subtask

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=f'{{"score": {raw_score}}}')]

    with patch("app.services.reviewer.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_resp

        score = asyncio.run(
            evaluate_subtask(
                prompt="タスク",
                result="結果",
                risk_level="low",
            )
        )

    assert 0.0 <= score <= 1.0
    assert score == pytest.approx(expected)


# ---------------------------------------------------------------------------
# test_update_trust_score
# ---------------------------------------------------------------------------


def test_update_trust_score(db):
    """指数移動平均 new = 0.8 * old + 0.2 * eval_score で更新されることを確認する。"""
    from app.services.agent_service import update_trust_score

    agent = Agent(
        name="TestAgent",
        description="テスト用",
        wallet_address="Wa11etAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        endpoint="https://example.com",
        trust_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    updated = update_trust_score(db, agent.agent_id, eval_score=1.0)

    # 0.8 * 0.5 + 0.2 * 1.0 = 0.6
    assert updated.trust_score == pytest.approx(0.6)


def test_update_trust_score_decreasing(db):
    """評価スコアが低い場合はtrust_scoreが下がることを確認する。"""
    from app.services.agent_service import update_trust_score

    agent = Agent(
        name="TestAgent2",
        description="テスト用2",
        wallet_address="Wa11etBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        endpoint="https://example2.com",
        trust_score=0.8,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    updated = update_trust_score(db, agent.agent_id, eval_score=0.0)

    # 0.8 * 0.8 + 0.2 * 0.0 = 0.64
    assert updated.trust_score == pytest.approx(0.64)
