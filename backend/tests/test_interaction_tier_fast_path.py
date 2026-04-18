import json
from pathlib import Path
from typing import Any, Dict

import pytest

import mcp_server
from db.sqlite_client import SQLiteClient
from runtime_state import SessionRecentReadCache


async def _noop_async(*_: Any, **__: Any) -> None:
    return None


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


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


@pytest.mark.asyncio
async def test_search_memory_accepts_scope_hint_deep_as_interaction_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient()
    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    raw = await mcp_server.search_memory(
        query="deep compare past release rationale",
        include_session=False,
        scope_hint="deep",
    )
    payload = json.loads(raw)

    assert payload["interaction_tier"] == "deep"
    assert payload["scope_hint"] is None
    assert payload["scope_hint_applied"] is False
    assert payload["scope_strategy_applied"] == "none"
    assert fake_client.received_filters == {}


@pytest.mark.asyncio
async def test_search_memory_keeps_fast_tier_candidate_cap_for_temporal_queries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = SQLiteClient(_sqlite_url(tmp_path / "interaction-tier-fast-cap.db"))
    await client.init_db()
    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    try:
        raw = await mcp_server.search_memory(
            query="when did we rebuild index",
            include_session=False,
        )
    finally:
        await client.close()

    payload = json.loads(raw)

    assert payload["interaction_tier"] == "fast"
    assert payload["intent"] == "temporal"
    assert payload["candidate_multiplier"] == 4
    assert payload["candidate_multiplier_applied"] == 4


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
        self.children = [
            {
                "domain": "core",
                "path": "agent/foo/child-1",
                "priority": 1,
                "disclosure": "When I need child one",
                "content_snippet": "child one",
            }
        ]

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

    async def get_children(self, memory_id: int):
        assert memory_id == self.memory["id"]
        return [dict(item) for item in self.children]


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


@pytest.mark.asyncio
async def test_read_memory_fast_path_invalidates_when_child_topology_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _ReadClient(content="parent body")
    render_calls = 0

    async def _fake_fetch_and_format_memory(*_args: Any, **_kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        child_paths = ",".join(item["path"] for item in fake_client.children)
        return f"CHILDREN: {child_paths}"

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _fake_fetch_and_format_memory)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    first = await mcp_server.read_memory("core://agent/foo")
    fake_client.children.append(
        {
            "domain": "core",
            "path": "agent/foo/child-2",
            "priority": 1,
            "disclosure": "When I need child two",
            "content_snippet": "child two",
        }
    )
    second = await mcp_server.read_memory("core://agent/foo")

    assert first == "CHILDREN: agent/foo/child-1"
    assert second == "CHILDREN: agent/foo/child-1,agent/foo/child-2"
    assert render_calls == 2


@pytest.mark.asyncio
async def test_recent_read_cache_refreshes_entry_recency_on_hit() -> None:
    cache = SessionRecentReadCache()
    cache._max_entries_per_session = 2

    await cache.remember(
        session_id="session-lru",
        uri="core://agent/a",
        state_token="state-a",
        payload="payload-a",
    )
    await cache.remember(
        session_id="session-lru",
        uri="core://agent/b",
        state_token="state-b",
        payload="payload-b",
    )

    assert (
        await cache.get(
            session_id="session-lru",
            uri="core://agent/a",
            state_token="state-a",
        )
    ) == "payload-a"

    await cache.remember(
        session_id="session-lru",
        uri="core://agent/c",
        state_token="state-c",
        payload="payload-c",
    )

    assert sorted(cache._values["session-lru"].keys()) == ["core://agent/a", "core://agent/c"]
