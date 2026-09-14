"""The PostgreSQL agent stores: same answers as the JSON stores, safe across workers.

Parity is checked by running one scenario through both backends and comparing
what callers see. Concurrency is checked the way two workers would collide:
separate store objects, several threads, one database.

Every row is written under a key unique to this run and removed afterwards, so
this can run against the live database like the other opt-in tests:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA = REPO_ROOT / "crawlernest" / "crawlernest-schema" / "agent_state_postgresql.sql"


def _dsn() -> str:
    return (
        f"host={os.getenv('CRAWLERNEST_PG_HOST', 'localhost')} "
        f"port={os.getenv('CRAWLERNEST_PG_PORT', '5432')} "
        f"dbname={os.getenv('CRAWLERNEST_PG_DATABASE', 'clawer')} "
        f"user={os.getenv('CRAWLERNEST_PG_USER', 'test')} "
        f"password={os.getenv('CRAWLERNEST_PG_PASSWORD', '')}"
    )


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class _PgCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from crawlernest.agent.persistence.postgres import ConnectionPool

        cls.pool = ConnectionPool(_dsn(), max_connections=8)
        with cls.pool.transaction() as cur:
            cur.execute(SCHEMA.read_text(encoding="utf-8"))
        cls.pool.verify_schema()

    @classmethod
    def tearDownClass(cls):
        cls.pool.close()

    def setUp(self):
        self.tag = f"pgtest-{uuid.uuid4().hex[:12]}"

    def tearDown(self):
        with self.pool.transaction() as cur:
            cur.execute("DELETE FROM agent_state.long_term_memory WHERE user_id LIKE %s", (f"{self.tag}%",))
            cur.execute("DELETE FROM agent_state.strategy WHERE engine = %s", (self.tag,))
            cur.execute("DELETE FROM agent_state.experience WHERE engine = %s", (self.tag,))
            cur.execute("DELETE FROM agent_state.patch WHERE document ->> 'task' = %s", (self.tag,))
            cur.execute("DELETE FROM agent_state.conversation_turn WHERE session_id LIKE %s", (f"{self.tag}%",))


class TestStrategyStore(_PgCase):
    def _both(self):
        from crawlernest.agent.persistence.postgres_stores import PostgresStrategyStore
        from crawlernest.agent.self_improvement.strategy_store import StrategyStore

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return StrategyStore(path=f"{tmp.name}/s.json"), PostgresStrategyStore(self.pool)

    def test_callers_see_the_same_answers_from_either_backend(self):
        def strip(entries):
            return [{k: v for k, v in e.items() if k not in {"id", "created_at", "updated_at"}} for e in entries]

        views = []
        for store in self._both():
            first = store.upsert(engine=self.tag, task_kind="dev_fix", strategy=["a", " "], confidence=0.9,
                                 reason="r", target=" Parser ")
            store.upsert(engine=self.tag, task_kind="dev_fix", strategy=["b"], confidence=0.7, reason="r2",
                         target="parser")
            store.upsert(engine=self.tag, task_kind="dev_fix", strategy=["c"], confidence=0.6, reason="r3")
            store.record_outcome(strategy_id=first["id"], success=True)
            store.record_outcome(strategy_id=first["id"], success=False)
            store.record_outcome(strategy_id=first["id"], success=True)
            self.assertIsNone(store.record_outcome(strategy_id=str(uuid.uuid4()), success=True))
            views.append(strip(store.query(engine=self.tag, task_kind="dev_fix", target="PARSER", limit=5)))
        json_view, pg_view = views
        self.assertEqual(json_view, pg_view)
        self.assertEqual(["b"], pg_view[0]["strategy"], "the upsert replaced the entry in place")
        self.assertEqual((2, 1), (pg_view[0]["success_count"], pg_view[0]["failure_count"]))

    def test_rollback_takes_a_strategy_out_of_active_queries(self):
        _, store = self._both()
        entry = store.upsert(engine=self.tag, task_kind="k", strategy=["x"], confidence=0.9, reason="r")
        rolled = store.rollback(strategy_id=entry["id"], reason="regressed")
        self.assertEqual("rolled_back", rolled["status"])
        self.assertEqual([], store.query(engine=self.tag, task_kind="k"))
        self.assertEqual(1, len(store.query(engine=self.tag, task_kind="k", require_active=False)))

    def test_concurrent_upserts_of_one_key_make_one_row(self):
        from crawlernest.agent.persistence.postgres_stores import PostgresStrategyStore

        errors: list[BaseException] = []

        def worker(n):
            try:
                PostgresStrategyStore(self.pool).upsert(
                    engine=self.tag, task_kind="k", strategy=[f"s{n}"], confidence=0.8, reason=str(n)
                )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual([], errors)
        with self.pool.transaction() as cur:
            cur.execute("SELECT count(*) FROM agent_state.strategy WHERE engine = %s", (self.tag,))
            self.assertEqual(1, cur.fetchone()[0])

    def test_concurrent_outcomes_are_all_counted(self):
        from crawlernest.agent.persistence.postgres_stores import PostgresStrategyStore

        entry = PostgresStrategyStore(self.pool).upsert(
            engine=self.tag, task_kind="k", strategy=["x"], confidence=0.9, reason="r"
        )
        threads = [
            threading.Thread(
                target=lambda: PostgresStrategyStore(self.pool).record_outcome(strategy_id=entry["id"], success=True)
            )
            for _ in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        final = PostgresStrategyStore(self.pool).query(engine=self.tag, task_kind="k")[0]
        self.assertEqual(20, final["success_count"], "a lost update would leave fewer")


class TestLongTermMemoryStore(_PgCase):
    def _scenario(self, store, user):
        store.insert(memory_type="user_preference", content="prefers UK",
                     metadata={"user_id": user, "entities": ["United Kingdom"]}, importance=0.4)
        store.insert(memory_type="user_preference", content="prefers UK",
                     metadata={"user_id": user, "entities": ["United Kingdom"], "source": "again"}, importance=0.8)
        store.insert(memory_type="entity_knowledge", content="asked about NTU",
                     metadata={"user_id": user, "entities": ["National Taiwan University"]}, importance=0.6)
        return [
            store.query(user_id=user, entities=["united kingdom"], types=["user_preference"]),
            store.query(user_id=user, entities=["nowhere at all"], types=None),
            store.query(user_id=user, types=["entity_knowledge"]),
            store.query(user_id=f"{user}-nobody"),
        ]

    def test_callers_see_the_same_memories_from_either_backend(self):
        from crawlernest.agent.memory_long_term.memory_store import LongTermMemoryStore
        from crawlernest.agent.persistence.postgres_stores import PostgresLongTermMemoryStore

        def view(results):
            return [
                [(e.type, e.content, e.importance, e.metadata.get("source"), round(e.decay_score, 3)) for e in result]
                for result in results
            ]

        with tempfile.TemporaryDirectory() as tmp:
            json_results = self._scenario(LongTermMemoryStore(path=f"{tmp}/m.json"), f"{self.tag}-u")
        pg_results = self._scenario(PostgresLongTermMemoryStore(self.pool), f"{self.tag}-u")
        self.assertEqual(view(json_results), view(pg_results))
        self.assertEqual(0.8, pg_results[0][0].importance, "a repeat merged and kept the higher importance")

    def test_a_user_is_trimmed_to_the_cap(self):
        from crawlernest.agent.persistence.postgres_stores import PostgresLongTermMemoryStore

        store = PostgresLongTermMemoryStore(self.pool, max_entries_per_user=3)
        user = f"{self.tag}-trim"
        for n in range(5):
            store.insert(memory_type="interaction_pattern", content=f"c{n}", metadata={"user_id": user}, importance=0.5)
        remaining = sorted(e.content for e in store.query(user_id=user, limit=10))
        self.assertEqual(["c2", "c3", "c4"], remaining)


class TestConversationAndLogs(_PgCase):
    def test_two_workers_share_one_history_capped_per_session(self):
        from crawlernest.agent.persistence.postgres_stores import PostgresConversationStore

        worker_a = PostgresConversationStore(self.pool, max_turns_per_session=4)
        worker_b = PostgresConversationStore(self.pool, max_turns_per_session=4)
        session = f"{self.tag}-s"
        for n in range(3):
            worker_a.append_user(session, content=f"q{n}", task_kind="data_query")
            worker_b.append_assistant(session, content=f"a{n}", task_kind="data_query")
        history = worker_b.get_history(session)
        self.assertEqual(["q1", "a1", "q2", "a2"], [t.content for t in history])
        self.assertEqual(["user", "assistant"] * 2, [t.role for t in history])
        worker_a.clear_session(session)
        self.assertEqual([], worker_b.get_history(session))

    def test_experiences_come_back_newest_first_and_filtered(self):
        from crawlernest.agent.persistence.postgres_stores import PostgresExperienceStore, PostgresPatchStore

        store = PostgresExperienceStore(self.pool)
        for n, target in enumerate(["parser", "extractor", "Parser"]):
            store.append(engine=self.tag, task_kind="dev_fix", task=f"t{n}", status="success",
                         final_score=1.4, tools_used=["a", ""], metadata={"target": target})
        recent = store.recent(engine=self.tag, target="PARSER")
        self.assertEqual(["t2", "t0"], [e["task"] for e in recent])
        self.assertEqual(1.0, recent[0]["final_score"])
        self.assertEqual(["a"], recent[0]["tools_used"])

        record = PostgresPatchStore(self.pool).append(
            task=self.tag, patch_candidate={}, patch_validation={"valid": True}, patch_execution={}
        )
        self.assertEqual("discarded", record["status"])


if __name__ == "__main__":
    unittest.main()
