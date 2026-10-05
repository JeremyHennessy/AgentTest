from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(EXPERIMENTS))
sys.path.insert(0, str(SCRIPTS))

for name in (
    "open_object_world",
    "open_object_world_explorer",
    "normalized_inquiry_objectives",
    "open_object_world_native_bridge",
    "open_object_world_action_association",
    "open_object_world_epistemic_actions",
    "open_object_world_epistemic_action_study",
    "open_object_world_copied_loop",
    "open_object_world_resolved_loop",
):
    location = (
        SCRIPTS / f"{name}.py"
        if name == "open_object_world_epistemic_action_study"
        else EXPERIMENTS / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(name, location)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

resolved = sys.modules["open_object_world_resolved_loop"]


class OpenObjectWorldResolvedLoopTests(unittest.TestCase):
    def make_core(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = StateStore(Path(temp.name) / "organism.json")
        state = initial_state()
        state["cycles"] = 20
        state["generation"] = 20
        state["agenda"]["started_cycle"] = 1
        store.save(state)
        return AgentCore(store)

    def test_falsifying_post_action_evidence_resolves_experiment(self):
        core = self.make_core()
        result = resolved.run_resolved_loop(
            core,
            seed=1,
            checkpoint=400,
        )
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertTrue(result["falsified_hypothesis"])
        self.assertEqual(result["resolved_experiment_status"], "completed")
        self.assertEqual(result["resolved_experiment_readiness"], "resolved")
        self.assertEqual(result["resolved_experiment_outcome"], "falsified")
        self.assertTrue(result["resolution_matches_observation"])
        self.assertEqual(
            result["resolution_evidence_refs"],
            [result["outcome_evidence_ref"]],
        )
        self.assertEqual(core.store.load()["cycles"], 20)

    def test_supporting_post_action_evidence_resolves_supported(self):
        core = self.make_core()
        result = resolved.run_resolved_loop(
            core,
            seed=1,
            checkpoint=600,
        )
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertFalse(result["falsified_hypothesis"])
        self.assertEqual(result["resolved_experiment_outcome"], "supported")
        self.assertTrue(result["resolution_matches_observation"])
        self.assertEqual(
            result["resolution_reflection"]["source"],
            "native_inquiry",
        )

    def test_public_outcome_evidence_followup_adaptation_diagnostic(self):
        world_mod = sys.modules["open_object_world"]
        selector_mod = sys.modules["open_object_world_epistemic_actions"]
        study_mod = sys.modules["open_object_world_epistemic_action_study"]
        bridge_mod = sys.modules["open_object_world_native_bridge"]

        rows = []
        for seed in range(1, 5):
            for checkpoint in range(200, 951, 50):
                world, attempts, observations, receipts = study_mod.run_to_checkpoint(
                    seed,
                    checkpoint,
                )
                ranked_before = study_mod.ranked_temporal(observations)
                selected_before = ranked_before[0]
                candidate_before = selected_before["candidate"]
                first_selection = selector_mod.select_epistemic_command(
                    observations[-1],
                    feature=candidate_before["feature"],
                    relation=candidate_before["relation"],
                    prefix_observations=observations,
                    prefix_receipts=receipts,
                )
                if first_selection["mode"] != "seek_disconfirming_observation":
                    rows.append(
                        {
                            "seed": seed,
                            "checkpoint": checkpoint,
                            "status": "not_mature",
                        }
                    )
                    continue

                before_observation = world_mod.observe_world(world)
                next_world, receipt = world_mod.transition(
                    deepcopy(world),
                    first_selection["command"],
                    cycle=checkpoint + 1,
                )
                after_observation = world_mod.observe_world(next_world)
                before_features = bridge_mod.public_features(before_observation)
                after_features = bridge_mod.public_features(after_observation)
                feature = candidate_before["feature"]
                evaluable = (
                    feature in before_features
                    and feature in after_features
                )
                if not evaluable:
                    rows.append(
                        {
                            "seed": seed,
                            "checkpoint": checkpoint,
                            "status": "not_evaluable",
                        }
                    )
                    continue

                changed = before_features[feature] != after_features[feature]
                falsified = (
                    changed
                    if candidate_before["relation"] == "same_next_observation"
                    else not changed
                )

                observations_after = [*observations, after_observation]
                receipts_after = [*receipts, receipt]
                ranked_after = study_mod.ranked_temporal(observations_after)
                selected_after = ranked_after[0]
                candidate_after = selected_after["candidate"]

                control_action = selector_mod.select_epistemic_command(
                    after_observation,
                    feature=candidate_before["feature"],
                    relation=candidate_before["relation"],
                    prefix_observations=observations,
                    prefix_receipts=receipts,
                )
                updated_same_inquiry_action = selector_mod.select_epistemic_command(
                    after_observation,
                    feature=candidate_before["feature"],
                    relation=candidate_before["relation"],
                    prefix_observations=observations_after,
                    prefix_receipts=receipts_after,
                )
                updated_top_action = selector_mod.select_epistemic_command(
                    after_observation,
                    feature=candidate_after["feature"],
                    relation=candidate_after["relation"],
                    prefix_observations=observations_after,
                    prefix_receipts=receipts_after,
                )

                matching_after = next(
                    (
                        item for item in ranked_after
                        if item["candidate"]["feature"] == candidate_before["feature"]
                        and item["candidate"]["relation"] == candidate_before["relation"]
                    ),
                    None,
                )
                score_after = (
                    matching_after["score"]
                    if matching_after is not None
                    else None
                )
                score_delta = (
                    round(score_after - selected_before["score"], 6)
                    if score_after is not None
                    else None
                )
                inquiry_changed = (
                    candidate_after["feature"],
                    candidate_after["relation"],
                ) != (
                    candidate_before["feature"],
                    candidate_before["relation"],
                )
                same_inquiry_action_changed = (
                    updated_same_inquiry_action["command"]
                    != control_action["command"]
                )
                next_behavior_changed = (
                    inquiry_changed
                    or updated_top_action["command"] != control_action["command"]
                )
                rows.append(
                    {
                        "seed": seed,
                        "checkpoint": checkpoint,
                        "status": "completed",
                        "falsified": falsified,
                        "initial_feature": candidate_before["feature"],
                        "initial_relation": candidate_before["relation"],
                        "updated_feature": candidate_after["feature"],
                        "updated_relation": candidate_after["relation"],
                        "score_delta_for_initial_inquiry": score_delta,
                        "inquiry_changed": inquiry_changed,
                        "same_inquiry_action_changed": same_inquiry_action_changed,
                        "next_behavior_changed": next_behavior_changed,
                    }
                )

        completed = [row for row in rows if row["status"] == "completed"]
        falsified_rows = [row for row in completed if row["falsified"]]
        supported_rows = [row for row in completed if not row["falsified"]]

        def count(group, field):
            return sum(bool(row[field]) for row in group)

        def score_decrease_count(group):
            return sum(
                row["score_delta_for_initial_inquiry"] is not None
                and row["score_delta_for_initial_inquiry"] < 0
                for row in group
            )

        summary = {
            "case_count": len(rows),
            "mature_evaluable_count": len(completed),
            "falsified_count": len(falsified_rows),
            "supported_count": len(supported_rows),
            "falsified_inquiry_changed_count": count(
                falsified_rows, "inquiry_changed"
            ),
            "supported_inquiry_changed_count": count(
                supported_rows, "inquiry_changed"
            ),
            "falsified_same_inquiry_action_changed_count": count(
                falsified_rows, "same_inquiry_action_changed"
            ),
            "supported_same_inquiry_action_changed_count": count(
                supported_rows, "same_inquiry_action_changed"
            ),
            "falsified_next_behavior_changed_count": count(
                falsified_rows, "next_behavior_changed"
            ),
            "supported_next_behavior_changed_count": count(
                supported_rows, "next_behavior_changed"
            ),
            "falsified_initial_inquiry_score_decreased_count": (
                score_decrease_count(falsified_rows)
            ),
            "supported_initial_inquiry_score_decreased_count": (
                score_decrease_count(supported_rows)
            ),
        }
        print(
            "OPEN_OBJECT_WORLD_FOLLOWUP_ADAPTATION "
            + json.dumps(summary, sort_keys=True)
        )

        self.assertEqual(summary["case_count"], 64)
        self.assertEqual(summary["mature_evaluable_count"], 30)
        self.assertEqual(
            summary["falsified_count"] + summary["supported_count"],
            30,
        )

    def test_resolved_loop_never_uses_core_action_labs(self):
        source = (
            EXPERIMENTS / "open_object_world_resolved_loop.py"
        ).read_text()
        self.assertNotIn("action_lab=True", source)
        self.assertNotIn("planning_lab=True", source)


if __name__ == "__main__":
    unittest.main()
