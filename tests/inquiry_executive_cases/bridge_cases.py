"""Synthetic bridge controls; no natural selection or learning evidence."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

import inquiry_executive
import agenttest.core as core_module
from agenttest.core import AgentCore
from agenttest.native_inquiry import NATIVE_INQUIRY_VERSION
from agenttest.state import initial_state
from inquiry_executive.bridge import MemoryStore, run_cycle
from inquiry_executive.synthetic import FIXTURE_TIME, create_sources

INPUTS = {"planning_lab_requested": True, "provenance": "synthetic_control"}


class OrdinaryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = create_sources(self.root / "sources")
        self.state = json.loads(self.fixture["ora"].read_text())

    def run_bridge(self, state=None, inputs=None):
        return run_cycle(self.state if state is None else state,
                         INPUTS if inputs is None else inputs, self.fixture["ora"])

    def test_fixture_is_deterministic_and_honestly_synthetic(self):
        second = create_sources(self.root / "second")
        self.assertEqual(self.fixture["provenance"]["source_sha256"], second["provenance"]["source_sha256"])
        self.assertEqual(self.fixture["provenance"]["label"], "synthetic_control")
        self.assertEqual(self.fixture["provenance"]["synthetic_prefix_action_count"], 3)
        self.assertEqual(self.fixture["provenance"]["ordinary_cycles_run_during_fixture_creation"], 0)
        self.assertFalse(self.fixture["provenance"]["selector_overrides"])
        self.assertTrue(self.fixture["provenance"]["closed_legacy_question_ids"])

    def test_memory_store_keeps_precommit_snapshot_until_save(self):
        store = MemoryStore(self.state, self.fixture["ora"])
        first = store.load()
        first["cycles"] += 100
        first["questions"][0]["text"] = "caller mutation"
        self.assertEqual(store.load(), self.state)
        store.save(first)
        saved = deepcopy(first)
        first["cycles"] += 100
        self.assertEqual(store.load(), saved)
        event = {"event": "example", "nested": []}
        store.append_journal(event)
        event["nested"].append("mutated")
        self.assertEqual(store.events, [{"event": "example", "nested": []}])
        store.events[0]["nested"].append("another mutation")
        self.assertEqual(store.events[0]["nested"], [])

    def test_exactly_one_real_cycle_and_no_labs_provider_or_scratch_store(self):
        original = AgentCore.cycle
        with patch.object(AgentCore, "cycle", autospec=True, side_effect=original) as cycle, \
             patch("agenttest.core.step_action_lab", side_effect=AssertionError("action lab")), \
             patch("agenttest.core.step_planning_lab", side_effect=AssertionError("planning lab")), \
             patch("agenttest.core.run_cognition", side_effect=AssertionError("provider")), \
             patch("agenttest.core.StateStore", side_effect=AssertionError("recursive scratch store")):
            result = self.run_bridge()
        self.assertEqual(cycle.call_count, 1)
        args = result["pre_inputs"]["cycle_kwargs"]
        self.assertIsNone(args["observation"])
        self.assertIsNone(args["cognition_provider"])
        for name in ("cognition", "action_lab", "planning_lab", "_phase42_counterfactual",
                     "_withhold_current_prediction_evidence", "copy_early_public_admission",
                     "copy_frontier_grounded_handoff", "copy_public_resolution_dispatch"):
            self.assertIs(args[name], False)
        for name in ("copy_public_observations", "copy_public_capacity", "stimulus"):
            self.assertIsNone(args[name])
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["pre_state"]["action_lab"], result["post_state"]["action_lab"])
        self.assertEqual(result["pre_state"]["planning_lab"], result["post_state"]["planning_lab"])
        self.assertEqual(result["treatments"]["planning_lab_actuation"], "deferred_by_inquiry_executive")
        self.assertEqual(result["treatments"]["original_requested_planning_mode"], "enabled")
        self.assertEqual(result["treatments"]["repository_observation"], "omitted_by_first_slice")
        self.assertEqual(result["treatments"]["legacy_resumption_diagnostic"], "no_current_prediction_evidence")

    def test_cycle_does_not_mutate_caller_or_any_source_file(self):
        before = deepcopy(self.state)
        sources = {key: self.fixture[key].read_bytes() for key in ("ora", "world", "observations")}
        result = self.run_bridge()
        self.assertEqual(self.state, before)
        for key, payload in sources.items():
            self.assertEqual(self.fixture[key].read_bytes(), payload)
        result["post_state"]["questions"][0]["text"] = "discarded output mutation"
        self.assertEqual(self.state, before)
        self.assertFalse((self.fixture["ora"].parent / "journal.jsonl").exists())

    def test_native_winner_is_actual_distinct_agenda_choice_and_exact_owned_experiment(self):
        result = self.run_bridge()
        selected = result["selection"]
        ordinary = result["result"]
        self.assertTrue(selected["owned"])
        self.assertEqual(selected["question_id"], self.fixture["question_id"])
        self.assertEqual(selected["experiment_id"], self.fixture["experiment_id"])
        self.assertEqual(ordinary["experiment"]["native_inquiry_candidate_id"],
                         self.state["experiments"][0]["native_inquiry_candidate_id"])
        self.assertEqual(ordinary["experiment_routing"]["relationship"], "owned")
        self.assertNotEqual(ordinary["agenda_decision"]["legacy_counterfactual"]["question_id"], selected["question_id"])
        self.assertEqual(result["post_state"]["agenda"]["decisions"][-1], ordinary["agenda_decision"])
        self.assertEqual(result["post_state"]["agenda"]["foreground_thread_id"], selected["thread_id"])

    def test_unmapped_and_less_than_two_eligible_are_truthful_null_controls(self):
        for case in ("unmapped", "no_decision"):
            fixture = create_sources(self.root / case, case=case)
            state = json.loads(fixture["ora"].read_text())
            result = run_cycle(state, INPUTS, fixture["ora"])
            if case == "unmapped":
                self.assertIsNotNone(result["selection"])
                self.assertNotEqual(result["selection"]["question_id"], fixture["question_id"])
                self.assertNotIn("native_inquiry", result["result"]["experiment"])
            else:
                self.assertIsNone(result["selection"])
                self.assertIsNone(result["result"]["agenda_decision"])
                self.assertIsNone(result["candidate_summary"]["candidate_count"])
                self.assertEqual(result["candidate_summary"]["summaries"], [])

    def test_real_intention_followup_does_not_grant_experiment_ownership(self):
        fixture = create_sources(self.root / "followup", case="unmapped")
        state = json.loads(fixture["ora"].read_text())
        state["cycles"] = state["generation"] = 1
        text = f"What obtainable evidence would resolve pending experiment {fixture['experiment_id']} with the least additional assumption?"
        result = self.run_bridge(state)
        self.assertEqual(result["selection"]["question"]["text"], text)
        self.assertNotEqual(result["selection"]["question_id"], fixture["question_id"])
        self.assertEqual(result["selection"]["experiment_id"], fixture["experiment_id"])
        self.assertEqual(result["selection"]["experiment_routing"]["relationship"], "explicit_followup")
        self.assertFalse(result["selection"]["owned"])
        self.assertEqual(result["selection"]["deferral_reason"], "no_owned_returned_experiment")

    def test_every_caller_envelope_expansion_is_rejected_before_cycle(self):
        fields = ("observation", "cognition", "cognition_provider", "planning_lab", "action_lab",
                  "_phase42_counterfactual", "_withhold_current_prediction_evidence", "legacy_question",
                  "selected", "selector", "copy_public_observations", "copy_early_public_admission",
                  "copy_frontier_grounded_handoff", "copy_public_capacity",
                  "copy_public_resolution_dispatch", "_now_override", "strict_experiment_admission")
        with patch.object(AgentCore, "cycle", side_effect=AssertionError("cycle must not run")):
            for field in fields:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.run_bridge(inputs={**INPUTS, field: True})
            for inputs in ({}, {"planning_lab_requested": 1, "provenance": "synthetic_control"},
                           {"planning_lab_requested": False, "provenance": "natural_success"}):
                with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                    self.run_bridge(inputs=inputs)

    def test_default_live_alias_symlink_and_hardlink_paths_are_rejected(self):
        paths = [ROOT / "state" / "organism.json", ROOT / "state" / "other.json", Path("state/organism.json")]
        symlink = self.root / "symlink.json"
        symlink.symlink_to(self.fixture["ora"])
        hardlink = self.root / "hardlink.json"
        # Keep the original fixture unaliased after this case.
        alias_source = self.root / "alias-source.json"
        alias_source.write_text("{}")
        os.link(alias_source, hardlink)
        paths.extend([symlink, hardlink, self.root / "sources" / ".." / "other.json"])
        for path in paths:
            with self.subTest(path=str(path)), self.assertRaises(ValueError):
                run_cycle(self.state, INPUTS, path)

    def test_non_json_and_duplicate_identity_fail_before_core(self):
        cases = []
        for key, value in (("callback", lambda: None), ("nonfinite", float("nan")), ("infinity", float("inf"))):
            state = deepcopy(self.state); state[key] = value; cases.append(state)
        duplicate = deepcopy(self.state); duplicate["questions"].append(deepcopy(duplicate["questions"][0])); cases.append(duplicate)
        with patch.object(AgentCore, "cycle", side_effect=AssertionError("cycle must not run")):
            for index, state in enumerate(cases):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    self.run_bridge(state)

    def test_fabricated_result_cannot_match_saved_ordinary_event(self):
        original = AgentCore.cycle
        mutations = (
            lambda result: result["question"].update(id="Qfabricated"),
            lambda result: result["agenda_decision"].update(selected_thread_id="ATfabricated"),
            lambda result: result["experiment_routing"].update(relationship="unrelated"),
        )
        for index, mutate in enumerate(mutations):
            def changed(core, **kwargs):
                result = original(core, **kwargs)
                mutate(result)
                return result
            with self.subTest(index=index), patch.object(AgentCore, "cycle", autospec=True, side_effect=changed), self.assertRaises(ValueError):
                self.run_bridge()

    def test_retained_candidate_summary_discloses_bound_without_second_selection(self):
        memory = MemoryStore(self.state, self.fixture["ora"])
        core = AgentCore(memory)
        source = self.state["experiments"][0]
        for index in range(5):
            candidate = {"version": NATIVE_INQUIRY_VERSION, "id": f"NIC:extra-control:{index}",
                "objective": "information_gain", "objective_score": .5,
                "relation": deepcopy(source["native_inquiry"]["relation"]),
                "question": f"Synthetic competing explanation number {index}: what will the observed public value do?",
                "hypothesis": source["hypothesis"], "method": source["method"] + f" Control {index}.",
                "falsification": source["falsification"], "predicted_observation": source["predicted_observation"],
                "evidence_refs": source["native_inquiry"]["evidence_refs"]}
            core.propose_native_inquiry(candidate, enabled=True, persist=True)
        result = self.run_bridge(memory.load())
        summary = result["candidate_summary"]
        self.assertEqual(summary["candidate_count"], 7)
        self.assertEqual(summary["retained_count"], 4)
        self.assertTrue(summary["truncated"])
        self.assertFalse(summary["complete_preselection_manifest"])
        self.assertIn("not instrumented", summary["disclosure"])

    def test_no_prediction_branch_restores_exact_provisional_resumption_accounting(self):
        state = deepcopy(self.state)
        q1, q2 = state["questions"][:2]
        q1["thread_evidence_refs"] = [state["episodes"][0]["id"]]
        agenda = state["agenda"]
        agenda.update(foreground_thread_id="AT000002", next_thread_index=3,
                      genuine_resumption_count=3, last_genuine_resumption={"synthetic_prior": True})
        agenda["threads"] = [
            {"id": "AT000001", "question_id": q1["id"], "status": "suspended", "created_cycle": 7, "history": [], "thread_progress_evidence_refs": []},
            {"id": "AT000002", "question_id": q2["id"], "status": "foreground", "created_cycle": 7, "history": [], "thread_progress_evidence_refs": []},
        ]
        original = AgentCore.cycle
        with patch.object(AgentCore, "cycle", autospec=True, side_effect=original) as cycle, \
             patch("agenttest.core.StateStore", side_effect=AssertionError("recursive scratch store")):
            result = self.run_bridge(state)
        self.assertEqual(cycle.call_count, 1)
        ordinary = result["result"]["agenda_decision"]
        self.assertEqual(ordinary["resumed_thread_id"], "AT000001")
        diagnostic = ordinary["resumption_causal_counterfactual"]
        self.assertEqual(diagnostic["reason"], "no_current_prediction_evidence_to_withhold")
        self.assertFalse(diagnostic["evaluated"])
        self.assertFalse(diagnostic["causal"])
        self.assertFalse(ordinary["priority_change_supported_by_new_evidence"])
        self.assertEqual(result["post_state"]["agenda"]["genuine_resumption_count"], 3)
        self.assertEqual(result["post_state"]["agenda"]["last_genuine_resumption"], {"synthetic_prior": True})

    def test_full_result_state_and_event_equal_plain_ordinary_disabled_lab_cycle(self):
        with patch("agenttest.core.utc_now", return_value=FIXTURE_TIME):
            bridged = self.run_bridge()
            memory = MemoryStore(self.state, self.fixture["ora"])
            ordinary = AgentCore(memory).cycle(**bridged["pre_inputs"]["cycle_kwargs"])
        self.assertEqual(bridged["result"], ordinary)
        self.assertEqual(bridged["post_state"], memory.load())
        self.assertEqual(bridged["events"], memory.events)
        self.assertEqual(bridged["pre_state"], self.state)

    def test_bridge_does_not_disable_normal_legacy_lab_modes(self):
        self.run_bridge()
        original_action = core_module.step_action_lab
        original_planning = core_module.step_planning_lab
        with patch("agenttest.core.step_action_lab", wraps=original_action) as action, \
             patch("agenttest.core.step_planning_lab", wraps=original_planning) as planning:
            a = AgentCore(MemoryStore(initial_state(), self.fixture["ora"])).cycle(action_lab=True)
            p = AgentCore(MemoryStore(initial_state(), self.fixture["ora"])).cycle(planning_lab=True)
        self.assertEqual(action.call_count, 1)
        self.assertEqual(planning.call_count, 1)
        self.assertIsNotNone(a["action_lab_result"])
        self.assertIsNotNone(p["planning_lab_result"])

    def test_two_actual_source_origins_do_not_hide_generic_second_routing(self):
        fixture = create_sources(self.root / "two-origins", case="two_inquiries")
        state = json.loads(fixture["ora"].read_text())
        self.assertEqual(fixture["proposal"]["origin_frame_sequence"], 4)
        self.assertEqual(fixture["competitor_proposal"]["origin_frame_sequence"], 6)
        self.assertEqual(fixture["provenance"]["synthetic_prefix_action_count"], 5)
        first = self.run_bridge(state)
        second = self.run_bridge(first["post_state"])
        third = self.run_bridge(second["post_state"])
        self.assertEqual(first["selection"]["question_id"], fixture["proposal"]["question_id"])
        self.assertEqual(first["selection"]["experiment_id"], fixture["proposal"]["experiment_id"])
        self.assertEqual(second["selection"]["question_id"], fixture["competitor_proposal"]["question_id"])
        self.assertNotEqual(second["selection"]["experiment_id"], fixture["competitor_proposal"]["experiment_id"])
        self.assertNotIn("native_inquiry", second["selection"]["experiment"])
        self.assertEqual(second["selection"]["experiment_routing"]["target_relationship"], "unrelated")
        self.assertEqual(third["selection"]["experiment_id"], fixture["proposal"]["experiment_id"])

    def test_three_fresh_process_actions_keep_original_binding_and_fresh_frames(self):
        from inquiry_executive.executive import InquiryExecutive
        research = self.root / "research"
        research.mkdir()
        path = research / "capsule.json"
        executive = InquiryExecutive.create(path, research_dir=research,
            source_paths={key: self.fixture[key] for key in ("ora", "world", "observations")}, enabled=True)
        inquiry = executive.admit(self.fixture["proposal"], executive.read()["revision"])
        origin = deepcopy(inquiry["origin"])
        code = """
import sys
from inquiry_executive.executive import InquiryExecutive
x=InquiryExecutive(sys.argv[1],research_dir=sys.argv[2],enabled=True)
d=x.select_next({'planning_lab_requested':True,'provenance':'synthetic_control'},x.read()['revision'])
assert d['attempt_id'] is not None, d['deferral_reason']
x.execute(d['attempt_id'],x.read()['revision'])
x.recover_or_interpret()
"""
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT / "experiments"))), PYTHONDONTWRITEBYTECODE="1")
        for _ in range(3):
            completed = subprocess.run([sys.executable, "-c", code, str(path), str(research)], env=env,
                                       capture_output=True, text=True, timeout=45)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        final = executive.read()
        self.assertEqual(len(final["inquiries"]), 1)
        self.assertEqual(final["inquiries"][0]["origin"], origin)
        self.assertEqual(final["counters"]["actions"], 3)
        self.assertEqual(final["counters"]["decisions"], 3)
        self.assertEqual(len({a["id"] for a in final["attempts"]}), 3)
        self.assertEqual(len({a["contract"]["frame_id"] for a in final["attempts"]}), 3)
        self.assertTrue(final["outcomes"][0]["receipt"]["blocked"])
        for decision in final["decisions"]:
            self.assertEqual(decision["inquiry_id"], inquiry["id"])
            self.assertEqual(decision["bridge"]["selection"]["experiment_id"], self.fixture["experiment_id"])
        self.assertEqual(len(final["beliefs"]), 3)
        self.assertTrue(all(a["status"] == "interpreted" for a in final["attempts"]))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
