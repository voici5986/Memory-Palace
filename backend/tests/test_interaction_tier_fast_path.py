import json
from typing import Any, Dict

import pytest

import mcp_server
from runtime_state import SessionRecentReadCache


async def _noop_async(*_: Any, **__: Any) -> None:
    return None


class _FakeClient:
    def __init__(self) -> None:
        self.received_filters: Dict[str, Any] = {}
        self.received_candidate_multiplier: int | None = None
        self.received_intent_profile: Dict[str, Any] = {}

    def preprocess_query(self, query: str) -> Dict[str, Any]:
        rewritten = " ".join(query.lower().split())
        return {
            "original_query": query,
            "normalized_query": rewritten,
            "rewritten_query": rewritten,
            "tokens": rewritten.split(),
            "changed": rewritten != query,
        }

    def classify_intent(self, _query: str, rewritten_query: str) -> Dict[str, Any]:
        if "deep" in rewritten_query:
            return {
                "intent": "exploratory",
                "strategy_template": "exploratory_broad",
                "method": "keyword_heuristic",
                "confidence": 0.75,
                "signals": ["deep_hint"],
            }
        return {
            "intent": "factual",
            "strategy_template": "factual_high_precision",
            "method": "keyword_heuristic",
            "confidence": 0.82,
            "signals": ["default_factual"],
        }

    async def search_advanced(
        self,
        *,
        query: str,
        mode: str,
        max_results: int,
        candidate_multiplier: int,
        filters: Dict[str, Any],
        intent_profile: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        _ = query
        _ = mode
        _ = max_results
        self.received_filters = dict(filters)
        self.received_candidate_multiplier = candidate_multiplier
        self.received_intent_profile = dict(intent_profile or {})
        return {
            "mode": "hybrid",
            "degraded": False,
            "degrade_reasons": [],
            "metadata": {
                "intent": self.received_intent_profile.get("intent"),
                "strategy_template": self.received_intent_profile.get(
                    "strategy_template"
                ),
                "candidate_multiplier_applied": candidate_multiplier,
            },
            "results": [
                {
                    "uri": "core://agent/index",
                    "memory_id": 1,
                    "snippet": "Index diagnostics",
                    "priority": 0,
                    "updated_at": "2026-03-01T12:00:00Z",
                    "metadata": {
                        "domain": "core",
                        "path": "agent/index",
                        "priority": 0,
                    },
                }
            ],
        }


@pytest.mark.asyncio
async def test_search_memory_defaults_to_fast_tier_without_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient()
    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    raw = await mcp_server.search_memory(
        query="recent release note",
        include_session=False,
    )
    payload = json.loads(raw)

    assert payload["interaction_tier"] == "fast"
    assert payload["intent_llm_attempted"] is False
    assert payload["candidate_multiplier"] == 4
    assert payload["candidate_multiplier_applied"] == 4


@pytest.mark.asyncio
async def test_search_memory_accepts_explicit_deep_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient()
    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    raw = await mcp_server.search_memory(
        query="deep compare past release rationale",
        include_session=False,
        filters={"interaction_tier": "deep"},
    )
    payload = json.loads(raw)

    assert payload["interaction_tier"] == "deep"
    assert payload["intent_llm_attempted"] is False
    assert payload["candidate_multiplier"] == 8
    assert fake_client.received_filters == {}


class _ReadClient:
    def __init__(self, *, content: str) -> None:
        self.memory: Dict[str, Any] = {
            "id": 7,
            "domain": "core",
            "path": "agent/foo",
            "title": "foo",
            "priority": 1,
            "disclosure": "When I need the foo memory",
            "created_at": "2026-04-17T10:00:00Z",
            "content": content,
        }

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = False,
    ) -> Dict[str, Any] | None:
        _ = reinforce_access
        if (domain, path) != ("core", "agent/foo"):
            return None
        return dict(self.memory)


@pytest.mark.asyncio
async def test_read_memory_known_uri_fast_path_reuses_recent_read_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _ReadClient(content="cached body")
    render_calls = 0

    async def _fake_fetch_and_format_memory(*_args: Any, **_kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        return "MEMORY: core://agent/foo"

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _fake_fetch_and_format_memory)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    first = await mcp_server.read_memory("core://agent/foo")
    second = await mcp_server.read_memory("core://agent/foo")

    assert first == "MEMORY: core://agent/foo"
    assert second == "MEMORY: core://agent/foo"
    assert render_calls == 1


@pytest.mark.asyncio
async def test_read_memory_fast_path_invalidates_when_state_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _ReadClient(content="first body")
    render_calls = 0

    async def _fake_fetch_and_format_memory(*_args: Any, **_kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        return f"MEMORY: {fake_client.memory['content']}"

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _fake_fetch_and_format_memory)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    first = await mcp_server.read_memory("core://agent/foo")
    fake_client.memory["content"] = "updated body"
    second = await mcp_server.read_memory("core://agent/foo")

    assert first == "MEMORY: first body"
    assert second == "MEMORY: updated body"
    assert render_calls == 2
