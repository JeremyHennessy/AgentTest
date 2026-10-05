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

    def test_persisted_native_evidence_recovers_selected_score_after_reload(self):
        from agenttest.native_evidence import (
            NATIVE_EVIDENCE_V2_VERSION,
            validate_native_evidence_payload,
        )

        world_mod = sys.modules["open_object_world"]
        selector_mod = sys.modules["open_object_world_epistemic_actions"]
        study_mod = sys.modules["open_object_world_epistemic_action_study"]
        bridge_mod = sys.modules["open_object_world_native_bridge"]
        objective_mod = sys.modules["normalized_inquiry_objectives"]

        rows = []
        for seed in range(1, 5):
            for checkpoint in range(200, 951, 50):
                with tempfile.TemporaryDirectory() as temp:
                    store = StateStore(Path(temp) / "organism.json")
                    state = initial_state()
                    state["cycles"] = 20
                    state["generation"] = 20
                    state["agenda"]["started_cycle"] = 1
                    store.save(state)
                    core = AgentCore(store)

                    world, attempts, observations, receipts = (
                        study_mod.run_to_checkpoint(seed, checkpoint)
                    )
                    ranked_before = study_mod.ranked_temporal(observations)
                    selected = ranked_before[0]
                    candidate = selected["candidate"]
                    epistemic = selector_mod.select_epistemic_command(
                        observations[-1],
                        feature=candidate["feature"],
                        relation=candidate["relation"],
                        prefix_observations=observations,
                        prefix_receipts=receipts,
                    )
                    if epistemic["mode"] != "seek_disconfirming_observation":
                        rows.append(
                            {
                                "seed": seed,
                                "checkpoint": checkpoint,
                                "status": "not_mature",
                            }
                        )
                        continue

                    staged = bridge_mod.stage_in_copied_core(
                        core,
                        selected,
                        observations,
                    )
                    experiment_id = staged["inquiry_result"]["experiment"]["id"]
                    grounding_ref = staged["evidence_result"]["evidence_ref"]

                    before_observation = world_mod.observe_world(world)
                    next_world, receipt = world_mod.transition(
                        deepcopy(world),
                        epistemic["command"],
                        cycle=checkpoint + 1,
                    )
                    after_observation = world_mod.observe_world(next_world)
                    before_features = bridge_mod.public_features(before_observation)
                    after_features = bridge_mod.public_features(after_observation)
                    feature = candidate["feature"]
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
                    supports = (
                        not changed
                        if candidate["relation"] == "same_next_observation"
                        else bool(changed)
                    )
                    outcome_evidence = {
                        "version": NATIVE_EVIDENCE_V2_VERSION,
                        "relation": {
                            "kind": candidate["relation"],
                            "feature": feature,
                            "action": None,
                            "comparison_status": "not_applicable",
                        },
                        "observation_refs": [
                            str(before_observation["observation_id"]),
                            str(after_observation["observation_id"]),
                        ],
                        "measurement_kind": "binary_transition_outcomes",
                        "measurement": {
                            "evaluable": 1,
                            "confirmations": 1 if supports else 0,
                            "refutations": 0 if supports else 1,
                        },
                    }
                    outcome_result = core.record_native_evidence(
                        outcome_evidence,
                        enabled=True,
                        persist=True,
                    )
                    core.resolve_native_inquiry(
                        experiment_id,
                        outcome_result["evidence_ref"],
                        enabled=True,
                        persist=True,
                    )

                    reloaded = AgentCore(StateStore(core.store.path))
                    reloaded_state = reloaded.store.load()
                    episode_by_id = {
                        str(item.get("id")): item
                        for item in reloaded_state.get("episodes", [])
                        if item.get("id")
                    }

                    def native_payload(ref):
                        episode = episode_by_id[str(ref)]
                        self.assertEqual(
                            episode.get("kind"),
                            "native_inquiry_evidence",
                        )
                        return validate_native_evidence_payload(
                            json.loads(str(episode.get("content") or ""))
                        )

                    grounding = native_payload(grounding_ref)
                    outcome = native_payload(outcome_result["evidence_ref"])
                    grounding_measurement = grounding["measurement"]
                    outcome_measurement = outcome["measurement"]
                    combined_confirmations = (
                        int(grounding_measurement["confirmations"])
                        + int(outcome_measurement["confirmations"])
                    )
                    combined_refutations = (
                        int(grounding_measurement["refutations"])
                        + int(outcome_measurement["refutations"])
                    )
                    combined_evaluable = (
                        combined_confirmations + combined_refutations
                    )
                    persisted_candidate = {
                        "id": "persisted-selected-inquiry",
                        "relation": candidate["relation"],
                        "feature": feature,
                        "action": None,
                        "status": "evaluated",
                        "evaluable": combined_evaluable,
                        "confirmations": combined_confirmations,
                        "refutations": combined_refutations,
                    }
                    recovered_score = objective_mod.rank_normalized_candidates(
                        [persisted_candidate],
                        "information_gain",
                    )[0]["score"]

                    observations_after = [*observations, after_observation]
                    ranked_after = study_mod.ranked_temporal(observations_after)
                    direct_match = next(
                        item
                        for item in ranked_after
                        if item["candidate"]["feature"] == feature
                        and item["candidate"]["relation"] == candidate["relation"]
                    )
                    direct_score = direct_match["score"]

                    parsed_native = []
                    for episode in reloaded_state.get("episodes", []):
                        if episode.get("kind") != "native_inquiry_evidence":
                            continue
                        parsed_native.append(
                            validate_native_evidence_payload(
                                json.loads(str(episode.get("content") or ""))
                            )
                        )
                    persisted_temporal_keys = {
                        (
                            item["relation"]["feature"],
                            item["relation"]["kind"],
                        )
                        for item in parsed_native
                        if item.get("measurement_kind")
                        == "binary_transition_outcomes"
                    }
                    direct_temporal_keys = {
                        (
                            item["candidate"]["feature"],
                            item["candidate"]["relation"],
                        )
                        for item in ranked_after
                        if item["eligible"]
                    }
                    action_association_evidence_count = sum(
                        item.get("measurement_kind")
                        == "comparative_action_exposure"
                        for item in parsed_native
                    )
                    resolved_experiment = next(
                        item
                        for item in reloaded_state["experiments"]
                        if item["id"] == experiment_id
                    )
                    rows.append(
                        {
                            "seed": seed,
                            "checkpoint": checkpoint,
                            "status": "completed",
                            "falsified": not supports,
                            "recovered_score": recovered_score,
                            "direct_score": direct_score,
                            "selected_score_matches_after_reload": (
                                recovered_score == direct_score
                            ),
                            "persisted_temporal_candidate_count": len(
                                persisted_temporal_keys
                            ),
                            "direct_temporal_candidate_count": len(
                                direct_temporal_keys
                            ),
                            "full_temporal_ranking_covered": (
                                direct_temporal_keys
                                <= persisted_temporal_keys
                            ),
                            "action_association_evidence_count": (
                                action_association_evidence_count
                            ),
                            "resolved_after_reload": (
                                resolved_experiment.get("status") == "completed"
                                and resolved_experiment.get("readiness") == "resolved"
                            ),
                        }
                    )

        completed = [row for row in rows if row["status"] == "completed"]
        summary = {
            "case_count": len(rows),
            "mature_evaluable_count": len(completed),
            "selected_score_match_count": sum(
                row["selected_score_matches_after_reload"]
                for row in completed
            ),
            "resolved_after_reload_count": sum(
                row["resolved_after_reload"] for row in completed
            ),
            "full_temporal_ranking_covered_count": sum(
                row["full_temporal_ranking_covered"]
                for row in completed
            ),
            "action_association_evidence_present_count": sum(
                row["action_association_evidence_count"] > 0
                for row in completed
            ),
            "min_direct_temporal_candidate_count": min(
                row["direct_temporal_candidate_count"]
                for row in completed
            ),
            "max_direct_temporal_candidate_count": max(
                row["direct_temporal_candidate_count"]
                for row in completed
            ),
            "min_persisted_temporal_candidate_count": min(
                row["persisted_temporal_candidate_count"]
                for row in completed
            ),
            "max_persisted_temporal_candidate_count": max(
                row["persisted_temporal_candidate_count"]
                for row in completed
            ),
        }
        print(
            "NATIVE_EVIDENCE_RELOAD_RECOVERY "
            + json.dumps(summary, sort_keys=True)
        )

        self.assertEqual(summary["case_count"], 64)
        self.assertEqual(summary["mature_evaluable_count"], 30)
        self.assertEqual(summary["selected_score_match_count"], 30)
        self.assertEqual(summary["resolved_after_reload_count"], 30)

    def test_resolved_loop_never_uses_core_action_labs(self):
        source = (
            EXPERIMENTS / "open_object_world_resolved_loop.py"
        ).read_text()
        self.assertNotIn("action_lab=True", source)
        self.assertNotIn("planning_lab=True", source)


if __name__ == "__main__":
    unittest.main()
