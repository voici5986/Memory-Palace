import json
from pathlib import Path
from typing import Any, Dict

import pytest

import mcp_server
from api import review as review_api
from db.sqlite_client import SQLiteClient
from db.snapshot import SnapshotManager
from models.schemas import RollbackRequest
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


class _AliasAwareReadClient:
    def __init__(self, *, content: str) -> None:
        base_memory = {
            "id": 7,
            "created_at": "2026-04-17T10:00:00Z",
            "content": content,
        }
        self.memories: Dict[tuple[str, str], Dict[str, Any]] = {
            (
                "core",
                "agent/foo",
            ): {
                **base_memory,
                "domain": "core",
                "path": "agent/foo",
                "priority": 1,
                "disclosure": "When I need the foo memory",
            },
            (
                "core",
                "agent/foo-alias",
            ): {
                **base_memory,
                "domain": "core",
                "path": "agent/foo-alias",
                "priority": 9,
                "disclosure": "When I need the alias view",
            },
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
        memory = self.memories.get((domain, path))
        if memory is None:
            return None
        return dict(memory)

    async def get_children(self, memory_id: int):
        assert memory_id == 7
        return [dict(item) for item in self.children]


class _AliasReadClient(_ReadClient):
    def __init__(self, *, content: str) -> None:
        super().__init__(content=content)
        self.alias_memory: Dict[str, Any] = {
            **self.memory,
            "path": "agent/foo-alias",
            "priority": 9,
            "disclosure": "alias disclosure",
        }

    async def get_memory_by_path(
        self,
        path: str,
        domain: str,
        reinforce_access: bool = False,
    ) -> Dict[str, Any] | None:
        _ = reinforce_access
        if domain != "core":
            return None
        if path == "agent/foo":
            return dict(self.memory)
        if path == "agent/foo-alias":
            return dict(self.alias_memory)
        return None


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
async def test_read_memory_alias_uri_fast_path_reuses_recent_read_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _AliasAwareReadClient(content="cached alias body")
    render_calls = 0

    async def _fake_fetch_and_format_memory(*args: Any, **_kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        return f"MEMORY: {args[1]}"

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _fake_fetch_and_format_memory)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    first = await mcp_server.read_memory("core://agent/foo-alias")
    second = await mcp_server.read_memory("core://agent/foo-alias")

    assert first == "MEMORY: core://agent/foo-alias"
    assert second == "MEMORY: core://agent/foo-alias"
    assert render_calls == 1


@pytest.mark.asyncio
async def test_read_memory_alias_and_canonical_uri_keep_distinct_cached_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _AliasAwareReadClient(content="shared content")
    render_calls = 0

    async def _fake_fetch_and_format_memory(*args: Any, **_kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        domain, path = mcp_server.parse_uri(args[1])
        memory = await fake_client.get_memory_by_path(path, domain)
        assert memory is not None
        return (
            f"MEMORY: {args[1]} | "
            f"priority={memory['priority']} | disclosure={memory['disclosure']}"
        )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _fake_fetch_and_format_memory)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    canonical_first = await mcp_server.read_memory("core://agent/foo")
    alias_first = await mcp_server.read_memory("core://agent/foo-alias")
    canonical_second = await mcp_server.read_memory("core://agent/foo")
    alias_second = await mcp_server.read_memory("core://agent/foo-alias")

    assert render_calls == 2
    assert canonical_first == canonical_second
    assert alias_first == alias_second
    assert canonical_first != alias_first
    assert "priority=1" in canonical_first
    assert "priority=9" in alias_first


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
async def test_read_memory_alias_fast_path_invalidates_when_alias_metadata_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _AliasReadClient(content="aliased body")
    render_calls = 0

    async def _fake_fetch_and_format_memory(_client: Any, uri: str, **_kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        path = uri.split("://", 1)[1]
        memory = await fake_client.get_memory_by_path(path, "core")
        assert memory is not None
        return (
            f"{memory['path']}|{memory['priority']}|"
            f"{memory['disclosure']}"
        )

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: fake_client)
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _fake_fetch_and_format_memory)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)

    first = await mcp_server.read_memory("core://agent/foo-alias")
    fake_client.alias_memory["priority"] = 4
    fake_client.alias_memory["disclosure"] = "updated alias disclosure"
    second = await mcp_server.read_memory("core://agent/foo-alias")

    assert first == "agent/foo-alias|9|alias disclosure"
    assert second == "agent/foo-alias|4|updated alias disclosure"
    assert render_calls == 2


@pytest.mark.asyncio
async def test_read_memory_fast_path_invalidates_when_rollback_restores_prior_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _ReadClient(content="version 1")
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
    fake_client.memory["content"] = "version 2"
    second = await mcp_server.read_memory("core://agent/foo")
    fake_client.memory["content"] = "version 1"
    third = await mcp_server.read_memory("core://agent/foo")

    assert first == "MEMORY: version 1"
    assert second == "MEMORY: version 2"
    assert third == "MEMORY: version 1"
    assert render_calls == 3


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
async def test_read_memory_fast_path_refreshes_after_rollback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "read-memory-fast-path-rollback.db"
    snapshots_dir = tmp_path / "snapshots"
    client = SQLiteClient(_sqlite_url(db_path))
    manager = SnapshotManager(str(snapshots_dir))
    await client.init_db()

    original_fetch = mcp_server._fetch_and_format_memory
    render_calls = 0
    session_id = "fast-path-rollback"

    async def _counting_fetch(*args: Any, **kwargs: Any) -> str:
        nonlocal render_calls
        render_calls += 1
        return await original_fetch(*args, **kwargs)

    monkeypatch.setattr(mcp_server, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(review_api, "get_sqlite_client", lambda: client)
    monkeypatch.setattr(mcp_server, "get_snapshot_manager", lambda: manager)
    monkeypatch.setattr(review_api, "get_snapshot_manager", lambda: manager)
    monkeypatch.setattr(mcp_server.runtime_state, "recent_reads", SessionRecentReadCache())
    monkeypatch.setattr(mcp_server, "_fetch_and_format_memory", _counting_fetch)
    monkeypatch.setattr(mcp_server, "_record_session_hit", _noop_async)
    monkeypatch.setattr(mcp_server, "_record_flush_event", _noop_async)
    monkeypatch.setattr(mcp_server, "_SESSION_ID", session_id)

    try:
        created = await client.create_memory(
            parent_path="",
            content="first body",
            priority=1,
            title="foo",
            domain="core",
        )
        assert created["uri"] == "core://foo"

        first = await mcp_server.read_memory("core://foo")
        second = await mcp_server.read_memory("core://foo")
        assert render_calls == 1
        assert "first body" in first
        assert second == first

        update_raw = await mcp_server.update_memory(
            "core://foo",
            old_string="first body",
            new_string="updated body",
        )
        update_payload = json.loads(update_raw)
        assert update_payload["updated"] is True

        updated = await mcp_server.read_memory("core://foo")
        assert "updated body" in updated
        assert render_calls == 2

        manifest = manager._load_manifest(session_id)
        snapshot_resource_id = next(iter(manifest["resources"].keys()))

        rollback_payload = await review_api.rollback_resource(
            session_id,
            snapshot_resource_id,
            RollbackRequest(),
        )
        assert rollback_payload.success is True

        rolled_back = await mcp_server.read_memory("core://foo")
        rolled_back_cached = await mcp_server.read_memory("core://foo")

        assert "first body" in rolled_back
        assert render_calls == 3
        assert rolled_back_cached == rolled_back
    finally:
        await client.close()


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
