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

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = True,
    ):
        _ = reinforce_access
        return self._current_by_uri.get(f"{domain}://{path}")


class _BatchSessionConsistencyClient(_SessionConsistencyClient):
    def __init__(self, current_by_uri, global_results):
        super().__init__(current_by_uri=current_by_uri, global_results=global_results)
        self.batch_calls = []
        self.single_calls = []

    async def get_memories_by_paths(self, path_requests, reinforce_access: bool = True):
        self.batch_calls.append(
            {
                "path_requests": list(path_requests),
                "reinforce_access": reinforce_access,
            }
        )
        return {
            f"{domain}://{path}": self._current_by_uri[f"{domain}://{path}"]
            for domain, path in path_requests
            if f"{domain}://{path}" in self._current_by_uri
        }

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = True,
    ):
        self.single_calls.append((domain, path, reinforce_access))
        raise AssertionError("single-path lookup should not run when batch lookup exists")


class _RaisingSessionConsistencyClient(_SessionConsistencyClient):
    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = True,
    ):
        _ = path, domain, reinforce_access
        raise RuntimeError("lookup exploded")


class _SingleLookupSessionConsistencyClient(_SessionConsistencyClient):
    def __init__(self, current_by_uri, global_results):
        super().__init__(current_by_uri=current_by_uri, global_results=global_results)
        self.single_calls = []

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = True,
    ):
        self.single_calls.append((domain, path, reinforce_access))
        return await super().get_memory_by_path(
            path,
            domain,
            reinforce_access=reinforce_access,
        )


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
async def test_search_memory_reapplies_filters_after_session_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SessionConsistencyClient(
        current_by_uri={
            "writer://chapter_1/note": {
                "id": 7,
                "content": "writer cached result",
                "priority": 1,
                "created_at": "2026-03-20T10:00:00Z",
            },
            "core://agent/current": {
                "id": 8,
                "content": "core global result",
                "priority": 1,
                "created_at": "2026-03-20T12:00:00Z",
            },
        },
        global_results=[
            {
                "uri": "core://agent/current",
                "memory_id": 8,
                "snippet": "core global result",
                "priority": 1,
                "score": 0.91,
                "updated_at": "2026-03-20T12:00:00Z",
            }
        ],
    )

    async def _fake_session_search(*, session_id, query, limit):
        _ = session_id, query, limit
        return [
            {
                "uri": "writer://chapter_1/note",
                "memory_id": 7,
                "snippet": "writer cached result",
                "priority": 1,
                "updated_at": "2026-03-20T10:00:00Z",
                "match_type": "session_queue",
                "source": "session_queue",
            }
        ]

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)
    monkeypatch.setattr(runtime_state.session_cache, "search", _fake_session_search)

    raw = await mcp_server.search_memory(
        "current result",
        mode="hybrid",
        max_results=5,
        include_session=True,
        filters={"domain": "core"},
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert [item["uri"] for item in payload["results"]] == ["core://agent/current"]
    assert payload["count"] == 1


@pytest.mark.asyncio
async def test_search_memory_uses_rewritten_query_for_session_cache_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SessionConsistencyClient(current_by_uri={}, global_results=[])
    observed_queries: list[str] = []

    def _rewrite_query(query: str):
        return {
            "original_query": query,
            "normalized_query": "normalized query",
            "rewritten_query": "normalized query",
            "tokens": ["normalized", "query"],
            "changed": True,
        }

    client.preprocess_query = _rewrite_query

    async def _fake_session_search(*, session_id, query, limit):
        _ = session_id, limit
        observed_queries.append(query)
        return []

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)
    monkeypatch.setattr(runtime_state.session_cache, "search", _fake_session_search)

    raw = await mcp_server.search_memory(
        "Original Query",
        mode="hybrid",
        max_results=5,
        include_session=True,
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert observed_queries == ["normalized query"]


@pytest.mark.asyncio
async def test_search_memory_drops_results_when_path_revalidation_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _RaisingSessionConsistencyClient(
        current_by_uri={},
        global_results=[
            {
                "uri": "core://agent/current",
                "memory_id": 7,
                "snippet": "stale snippet from session cache",
                "priority": 3,
                "score": 0.91,
                "updated_at": "2026-03-20T10:00:00Z",
            }
        ],
    )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    raw = await mcp_server.search_memory(
        "fresh content",
        mode="hybrid",
        max_results=5,
        include_session=False,
    )
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["results"] == []
    assert payload["count"] == 0
    assert payload["session_first_metrics"]["revalidate_lookup_failed"] == 1
    assert "path_revalidation_lookup_failed" in payload["degrade_reasons"]


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


@pytest.mark.asyncio
async def test_search_memory_uses_batch_revalidation_when_client_supports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _BatchSessionConsistencyClient(
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
    assert client.batch_calls == [
        {
            "path_requests": [("core", "agent/current")],
            "reinforce_access": False,
        }
    ]
    assert client.single_calls == []
    assert payload["session_first_metrics"]["session_queue_refreshed"] == 1


@pytest.mark.asyncio
async def test_search_memory_uses_non_reinforcing_single_revalidation_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _SingleLookupSessionConsistencyClient(
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
    assert client.single_calls == [("core", "agent/current", False)]
