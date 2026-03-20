import json

import pytest

import mcp_server
from runtime_state import runtime_state


async def _noop_async(*_args, **_kwargs):
    return None


class _SessionConsistencyClient:
    def __init__(self, current_by_uri, global_results):
        self._current_by_uri = dict(current_by_uri)
        self._global_results = list(global_results)

    def preprocess_query(self, query: str):
        return {
            "original_query": query,
            "normalized_query": query,
            "rewritten_query": query,
            "tokens": [token for token in query.lower().split() if token],
            "changed": False,
        }

    def classify_intent(self, _query: str, _query_effective: str):
        return {
            "intent": "factual",
            "strategy_template": "factual_high_precision",
            "method": "rule",
            "confidence": 1.0,
            "signals": ["test"],
        }

    async def search_advanced(
        self,
        *,
        query: str,
        mode: str,
        max_results: int,
        candidate_multiplier: int,
        filters,
        intent_profile,
    ):
        _ = query
        _ = mode
        _ = max_results
        _ = candidate_multiplier
        _ = filters
        _ = intent_profile
        return {
            "mode": "hybrid",
            "degraded": False,
            "degrade_reasons": [],
            "results": list(self._global_results),
            "metadata": {
                "intent": "factual",
                "strategy_template": "factual_high_precision",
                "candidate_multiplier_applied": 2,
            },
        }

    async def get_memory_by_path(self, path: str, domain: str):
        return self._current_by_uri.get(f"{domain}://{path}")


@pytest.mark.asyncio
async def test_search_memory_drops_deleted_session_cache_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SessionConsistencyClient(current_by_uri={}, global_results=[])
    session_results = [
        {
            "uri": "core://agent/deleted",
            "memory_id": 7,
            "snippet": "deleted memory still cached",
            "priority": 1,
            "updated_at": "2026-03-20T10:00:00Z",
            "match_type": "session_queue",
            "source": "session_queue",
        }
    ]

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)
    monkeypatch.setattr(runtime_state.session_cache, "search", _noop_async)

    async def _fake_session_search(*, session_id, query, limit):
        _ = session_id
        _ = query
        _ = limit
        return list(session_results)

    monkeypatch.setattr(runtime_state.session_cache, "search", _fake_session_search)

    raw = await mcp_server.search_memory(
        "deleted memory",
        mode="hybrid",
        max_results=5,
        include_session=True,
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["results"] == []
    assert payload["session_first_metrics"]["stale_result_dropped"] == 1
    assert payload["count"] == 0


@pytest.mark.asyncio
async def test_search_memory_refreshes_session_cache_hits_from_current_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SessionConsistencyClient(
        current_by_uri={
            "core://agent/current": {
                "id": 42,
                "content": "fresh content from database state",
                "priority": 0,
                "created_at": "2026-03-20T12:00:00Z",
            }
        },
        global_results=[],
    )
    session_results = [
        {
            "uri": "core://agent/current",
            "memory_id": 7,
            "snippet": "stale snippet from session cache",
            "priority": 3,
            "updated_at": "2026-03-20T10:00:00Z",
            "match_type": "session_queue",
            "source": "session_queue",
        }
    ]

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    async def _fake_session_search(*, session_id, query, limit):
        _ = session_id
        _ = query
        _ = limit
        return list(session_results)

    monkeypatch.setattr(runtime_state.session_cache, "search", _fake_session_search)

    raw = await mcp_server.search_memory(
        "fresh content",
        mode="hybrid",
        max_results=5,
        include_session=True,
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["results"][0]["uri"] == "core://agent/current"
    assert payload["results"][0]["memory_id"] == 42
    assert payload["results"][0]["priority"] == 0
    assert payload["results"][0]["snippet"] == "fresh content from database state"
    assert payload["session_first_metrics"]["session_queue_refreshed"] == 1


@pytest.mark.asyncio
async def test_search_memory_sorts_final_results_by_display_score_after_session_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SessionConsistencyClient(
        current_by_uri={
            "core://agent/low": {
                "id": 7,
                "content": "lower score candidate",
                "priority": 1,
                "created_at": "2026-03-20T12:00:00Z",
            },
            "core://agent/high": {
                "id": 8,
                "content": "higher score candidate",
                "priority": 1,
                "created_at": "2026-03-20T12:00:01Z",
            },
        },
        global_results=[
            {
                "uri": "core://agent/low",
                "memory_id": 7,
                "snippet": "lower score candidate",
                "priority": 1,
                "score": 0.15,
                "updated_at": "2026-03-20T12:00:00Z",
            },
            {
                "uri": "core://agent/high",
                "memory_id": 8,
                "snippet": "higher score candidate",
                "priority": 1,
                "score": 0.91,
                "updated_at": "2026-03-20T12:00:01Z",
            },
        ],
    )
    session_results = [
        {
            "uri": "core://agent/low",
            "memory_id": 7,
            "snippet": "stale session ordering candidate",
            "priority": 1,
            "score": 0.99,
            "updated_at": "2026-03-20T11:59:00Z",
            "match_type": "session_queue",
            "source": "session_queue",
        }
    ]

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    async def _fake_session_search(*, session_id, query, limit):
        _ = session_id
        _ = query
        _ = limit
        return list(session_results)

    monkeypatch.setattr(runtime_state.session_cache, "search", _fake_session_search)

    raw = await mcp_server.search_memory(
        "ordering regression",
        mode="hybrid",
        max_results=5,
        include_session=True,
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert [item["uri"] for item in payload["results"][:2]] == [
        "core://agent/high",
        "core://agent/low",
    ]
    assert payload["results"][0]["score"] == 0.91
    assert payload["results"][1]["score"] == 0.15
