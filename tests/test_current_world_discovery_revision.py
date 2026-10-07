"""Change-specific revision accounting and history/authority preservation checks."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenttest import current_world_investigation as investigation
from agenttest.grounded_policy import policy
from agenttest.grounded_policy.primitives import canonical, digest
from agenttest.heartbeat_claim import finish_heartbeat, verify_completed
from agenttest.planning_lab import initial_planning_lab_state, execute_investigation_action
from agenttest.state import initial_state, StateStore


def preserved_null_fixture(*, later=("north", "north", "north", "south", "south"), disabled=False):
    """A legacy-format null with genuine software-fixture actuator observations."""
    state = initial_state()
    state["planning_lab"] = initial_planning_lab_state()
    for cycle, action in enumerate(["north", "south"] * 16 + list(later), 1):
        state["cycles"] = state["generation"] = cycle
        execute_investigation_action(state, action=action,
            case_id=f"setup:{cycle}", attempt_id=f"setup:{cycle}")
    result = investigation.prepare_next_case(state, request_id="legacy:heartbeat")
    assert result["status"] == "null", result
    lane = state["current_world_investigation"]
    lane["version"] = investigation.LEGACY_VERSION
    if disabled:
        investigation.disable_prepared_case(state)
    return state, result


class CurrentWorldDiscoveryRevision(unittest.TestCase):
    def test_revision_preserves_archived_case_and_partitions_all_history_once(self):
        state, original_preparation = preserved_null_fixture(disabled=True)
        lane = state["current_world_investigation"]
        frozen = {key: canonical(lane[key]) for key in ("discovery", "cohort", "cases", "rollback")}
        original_history = deepcopy(state["planning_lab"]["transition_observations"])
        claim = {"request_id": "legacy:heartbeat", "claim_hash": "a" * 64,
                 "input_cycle": state["cycles"] - 1}
        state["current_world_heartbeat"] = {"pending": claim, "completed": [], "abandoned": []}
        event = {"event": "cycle", "cycle": state["cycles"], "planning_lab_result": {"action": None},
                 "current_world_preparation": original_preparation}
        finish_heartbeat(state, event, claim, "b" * 40)
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            store.save(state)
            store.append_journal(event)
            verify_completed(store.path, "legacy:heartbeat", require_current=True)
            state["cycles"] += 1
            with patch.object(policy, "build_cohort", wraps=policy.build_cohort) as build:
                result = investigation.prepare_next_case(state, request_id="revision:prepare")
                self.assertEqual(build.call_count, 1)
            self.assertEqual(result["status"], "prepared")
            lane = state["current_world_investigation"]
            for key in ("discovery", "cohort", "rollback"):
                self.assertEqual(canonical(lane[key]), frozen[key])
            self.assertEqual(canonical(lane["cases"][:1]), frozen["cases"])
            revision = lane["discovery_revisions"][0]
            old_case, case = lane["cases"]
            self.assertNotIn("discovery_revision_id", old_case)
            self.assertEqual(case["discovery_revision_hash"], revision["revision_hash"])
            self.assertTrue(revision["structural_changes"])
            self.assertEqual([ref["event_id"] for ref in revision["promoted_refs"]],
                             ["investigation_action:PX000035"])
            discovery, cohort, evidence = investigation.discovery_partition(lane, investigation.current_view(state), case)
            d_ids, u_ids = {row["event_id"] for row in discovery}, {row["event_id"] for row in evidence}
            self.assertFalse(d_ids & u_ids)
            self.assertEqual(d_ids | u_ids, {row["event_id"] for row in investigation.current_view(state)["rows"]})
            self.assertEqual(case["evidence_refs"], investigation._refs(evidence))
            self.assertEqual(case["decision"], policy.evaluate(cohort, case["decision"]["context"], evidence))
            old_d, old_cohort, old_u = investigation.discovery_partition(lane, investigation.current_view(state), old_case)
            self.assertEqual(len(old_d), 32)
            self.assertEqual(len(old_u), 5)
            self.assertEqual(old_cohort, lane["cohort"])
            self.assertEqual(state["planning_lab"]["transition_observations"], original_history)
            store.save(state)
            verify_completed(store.path, "legacy:heartbeat")
            # A saved revision/case reopens without another rebuild or selection.
            reloaded = store.load()
            before = canonical(reloaded["current_world_investigation"])
            with patch.object(policy, "build_cohort", side_effect=AssertionError("no repeated rebuild")):
                self.assertEqual(investigation.prepare_next_case(reloaded, request_id="revision:retry")["status"], "pending")
            self.assertEqual(canonical(reloaded["current_world_investigation"]), before)
            reloaded["cycles"] += 1
            owned = investigation.consume_prepared_case(reloaded, request_id="revision:consume")
            self.assertEqual(owned["case_id"], case["case_id"])
            self.assertEqual(owned["action"], "north")
            self.assertEqual(investigation.prepare_next_case(reloaded, request_id="revision:consume")["status"], "exhausted")
            self.assertEqual(reloaded["current_world_investigation"]["actions_remaining"], 1)
            self.assertEqual(len(reloaded["current_world_investigation"]["cases"]), 2)
            self.assertIsNone(investigation.consume_prepared_case(reloaded, request_id="revision:replay")["action"])
            store.save(reloaded)
            verify_completed(store.path, "legacy:heartbeat")

    def test_later_novel_rows_without_structural_change_do_not_create_case(self):
        state, _ = preserved_null_fixture(later=("east",))
        state["cycles"] += 1
        original_case = canonical(state["current_world_investigation"]["cases"][0])
        result = investigation.prepare_next_case(state, request_id="revision:no-structure")
        self.assertEqual(result["reason"], "no_structural_change")
        lane = state["current_world_investigation"]
        self.assertEqual(len(lane["cases"]), 1)
        self.assertEqual(lane["discovery_revisions"][0]["structural_changes"], [])
        self.assertEqual(canonical(lane["cases"][0]), original_case)
        self.assertEqual(lane["actions_remaining"], 2)
        with patch.object(policy, "build_cohort", side_effect=AssertionError("no repeated rebuild")):
            investigation.prepare_next_case(state, request_id="revision:repeat")
            investigation.disable_prepared_case(state)
            self.assertEqual(investigation.prepare_next_case(state, request_id="revision:toggle")["status"], "disabled")
        self.assertEqual(len(lane["discovery_revisions"]), 1)
        changed = deepcopy(lane["cohort"])
        for item in changed["actions"]:
            item["conditional_count"] += 1
        self.assertEqual(investigation.model_structure_changes(lane["cohort"], changed), [])

    def test_stale_revision_or_changed_source_rejects_without_action(self):
        for mutation in ("revision", "source", "execution"):
            with self.subTest(mutation=mutation):
                state, _ = preserved_null_fixture()
                state["cycles"] += 1
                investigation.prepare_next_case(state, request_id="revision:prepare")
                state["cycles"] += 1
                if mutation == "revision":
                    state["current_world_investigation"]["discovery_revisions"][0]["promoted_refs"][0]["sha256"] = "changed"
                if mutation == "source":
                    state["planning_lab"]["transition_observations"][33]["extra"] = "changed"
                before = canonical(state["planning_lab"])
                with patch.object(investigation, "execution_hash", return_value="changed" if mutation == "execution" else investigation.execution_hash()), \
                     patch.object(investigation, "execute_investigation_action", side_effect=AssertionError("stale authority acted")):
                    result = investigation.consume_prepared_case(state, request_id="revision:consume")
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(canonical(state["planning_lab"]), before)

    def test_pending_authority_and_rejected_staging_preserve_original_case(self):
        state, _ = preserved_null_fixture()
        state["cycles"] += 1
        investigation.prepare_next_case(state, request_id="revision:prepare")
        before = canonical(state["current_world_investigation"])
        self.assertEqual(investigation.prepare_next_case(state, request_id="revision:again")["status"], "pending")
        self.assertEqual(canonical(state["current_world_investigation"]), before)
        state, _ = preserved_null_fixture()
        original = deepcopy(state["current_world_investigation"])
        # Exercise only the changed staged-admission failure path, not a new
        # scientific profile or production limit.
        limit = len(canonical(original)) + 4096
        with patch.object(investigation, "CHECKPOINT_BYTES", limit):
            state["cycles"] += 1
            result = investigation.prepare_next_case(state, request_id="revision:too-large")
            self.assertEqual(result["status"], "blocked")
            retained = state["current_world_investigation"]
            self.assertEqual(retained["cases"], original["cases"])
            self.assertEqual(retained["discovery"], original["discovery"])
            self.assertEqual(retained["cohort"], original["cohort"])
            self.assertLessEqual(len(canonical(retained)), limit)
            self.assertEqual(retained["revision_attempt"]["status"], "blocked")
        with patch.object(policy, "build_cohort", side_effect=AssertionError("blocked revision retried")):
            investigation.prepare_next_case(state, request_id="revision:retry-blocked")

    def test_historical_context_promotion_limit_remains_source_ordered(self):
        seed = {"event_id": "seed", "before_context": {"position": [0, 0], "inventory_ids": None, "visible_ids": None},
                "action": "north", "after_position": [1, 0], "refs": {"before": "a" * 64, "receipt": "b" * 64, "after": "c" * 64}}
        rows = [seed]
        for index in range(40):
            row = deepcopy(seed)
            row.update(event_id=f"reverse-{40-index:03d}", action="east" if index < 25 else "west",
                       before_context={"position": [index % 5 - 2, (index // 5) % 5 - 2], "inventory_ids": None, "visible_ids": None},
                       after_position=[0, 0])
            rows.append(row)
        promoted = investigation._promotions([seed], rows, recipe=investigation.CONTEXT_REVISION_VERSION)
        self.assertEqual([row["event_id"] for row in promoted], [row["event_id"] for row in rows[1:33]])
        self.assertEqual(len(promoted), 32)


if __name__ == "__main__":
    unittest.main()
