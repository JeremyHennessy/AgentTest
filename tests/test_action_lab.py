from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agenttest.action_lab import (
    ACTION_ORDER,
    ensure_action_lab_state,
    step_action_lab,
)
from agenttest.change_control import PROTECTED_PATHS, make_change_manifest
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state


class BoundedActionLabTests(unittest.TestCase):
    def test_action_authority_is_protected(self) -> None:
        self.assertIn("src/agenttest/action_lab.py", PROTECTED_PATHS)
        self.assertIn(".github/workflows/growth.yml", PROTECTED_PATHS)

        state = initial_state()
        state["episodes"] = [
            {
                "id": "E000001",
                "cycle": 1,
                "kind": "stimulus",
                "content": "action evidence",
                "concepts": ["action"],
            }
        ]
        with self.assertRaises(ValueError):
            make_change_manifest(
                state,
                title="Rewrite action authority",
                target_dimension="agency",
                files=["src/agenttest/action_lab.py"],
                hypothesis="Changing action authority may alter behavior.",
                expected_effect="Different action behavior.",
                test_plan="Run checks.",
                falsification="No behavior change.",
                rollback="Revert.",
                evidence_refs=["E000001"],
            )

    def test_first_eight_actions_identify_all_hidden_transitions(self) -> None:
        state = initial_state()
        actions = []
        for cycle in range(1, 9):
            state["cycles"] = cycle
            result = step_action_lab(state)
            actions.append(result["action"])

        lab = state["action_lab"]

        self.assertEqual(actions, list(ACTION_ORDER) * 2)
        self.assertEqual(
            lab["learned_effects"]["north"]["modal_delta"],
            [1, 0],
        )
        self.assertEqual(
            lab["learned_effects"]["east"]["modal_delta"],
            [0, -1],
        )
        self.assertEqual(
            lab["learned_effects"]["south"]["modal_delta"],
            [-1, 0],
        )
        self.assertEqual(
            lab["learned_effects"]["west"]["modal_delta"],
            [0, 1],
        )
        self.assertTrue(
            all(
                lab["learned_effects"][action]["unblocked_samples"] == 2
                for action in ACTION_ORDER
            )
        )
        self.assertTrue(
            all(
                lab["learned_effects"][action]["confidence"] == 1.0
                for action in ACTION_ORDER
            )
        )

    def test_learned_transition_model_changes_later_action_choice(self) -> None:
        state = initial_state()
        for cycle in range(1, 9):
            state["cycles"] = cycle
            step_action_lab(state)

        state["cycles"] = 9
        result = step_action_lab(state)

        self.assertEqual(result["decision"]["kind"], "use_learned_transition")
        self.assertEqual(result["action"], "south")
        self.assertEqual(result["decision"]["predicted_target"], [-1, 0])
        self.assertEqual(result["after"], [-1, 0])
        self.assertGreater(result["visited_location_count"], 4)

    def test_action_history_persists_across_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            state = store.load()
            state["cycles"] = 1
            first = step_action_lab(state)
            store.save(state)

            reloaded = store.load()
            lab = ensure_action_lab_state(reloaded)

            self.assertEqual(len(lab["history"]), 1)
            self.assertEqual(lab["history"][0]["id"], first["id"])
            self.assertEqual(lab["position"], first["after"])

    def test_core_action_lab_turn_becomes_citable_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            core = AgentCore(store)

            result = core.cycle("bounded action", action_lab=True)
            state = store.load()

            self.assertIsNotNone(result["action_lab_result"])
            action_episode = next(
                item
                for item in state["episodes"]
                if item.get("kind") == "action_lab"
            )
            self.assertIn("causal_action", action_episode["concepts"])
            self.assertIn(
                result["action_lab_result"]["action"],
                action_episode["concepts"],
            )
            self.assertEqual(len(state["action_lab"]["history"]), 1)

    def test_default_cycle_grants_no_action_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "organism.json")
            core = AgentCore(store)

            result = core.cycle("ordinary cycle")
            state = store.load()

            self.assertIsNone(result["action_lab_result"])
            self.assertEqual(state["action_lab"]["history"], [])


if __name__ == "__main__":
    unittest.main()
