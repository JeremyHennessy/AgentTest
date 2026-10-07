from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "experiments"))

from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from challenge_eight_action_closed_loop import _agenda_identity, _stream_prefix
from challenge_retained_evidence_followup import (
    DEFAULT_FLAGS, PRODUCTION_FLAGS, production_pair, qualify_report, verified_payload,
    refresh_qualifications, resumption_accounting,
)
from challenge_retained_evidence_study import (
    digest, file_digest, fixed_clock, fixed_time, native_outcome_pair,
    repeat_measures, selector_pair,
)
from challenge_shadow_recorder import ChallengeShadowRecorder, single_transition_outcome, source_manifest
from native_observe_inquire_integration import observe_and_inquire_policy, stage_publication_inquiry
from open_object_world_challenge import initial_world, observe_world, transition


class RetainedEvidenceFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture_row(self):
        before = initial_world(1)
        after, receipt = transition(before, {"action": "north"}, cycle=1)
        candidate = {"feature": "position", "relation": "same_next_observation"}
        payload = single_transition_outcome(before=observe_world(before), after=observe_world(after), candidate=candidate)
        outcome = "supported" if payload["measurement"]["confirmations"] else "falsified"
        return {"candidate": candidate, "receipt": receipt, "outcome": outcome,
                "native_outcome_pair": {"outcome_payload_sha256": digest(payload)}}, payload

    def test_outcome_reconstruction_is_hash_checked(self):
        row, payload = self.fixture_row()
        self.assertEqual(verified_payload(row), payload)
        row["outcome"] = "supported" if row["outcome"] == "falsified" else "falsified"
        with self.assertRaisesRegex(ValueError, "original payload hash"):
            verified_payload(row)

    def test_foreground_counts_do_not_imply_native_action_scheduling(self):
        row, _ = self.fixture_row()
        observation = observe_world(initial_world(1))
        pair = selector_pair(observation, row["candidate"], [], self.root / "seed-1/selector-01")
        row.update({"step": 1, "question_id": "Q_STUDY", "selector_pair": pair,
                    "pre_action_native_cycle": {"selected_question_id": "Q_OTHER"},
                    "repetitions": {arm: repeat_measures([], observation, row["candidate"], pair[arm])
                                    for arm in ("retained", "ablated")}})
        report = {"layouts": [{"seed": 1, "rows": [row]}]}
        qualified = qualify_report(report, self.root)
        self.assertEqual(qualified["harness_scheduled_challenge_actions"], 1)
        self.assertEqual(qualified["study_question_foreground_selections_before_action"], 0)
        self.assertEqual(qualified["actions_without_study_question_foreground_selection"], 1)
        self.assertEqual(qualified["matched_repeat_effect_counts"]["retained"]["matched_disconfirmed_effect_opportunities"], 0)
        self.assertEqual(qualified["matched_repeat_effect_counts"]["retained"]["avoided_disconfirmed_effects"], 0)
        self.assertEqual(qualified["original_cycle_flags"], DEFAULT_FLAGS)
        altered = json.loads((self.root / "seed-1/selector-01/retained.json").read_text())
        altered["feature"] = "other"
        (self.root / "seed-1/selector-01/retained.json").write_text(json.dumps(altered))
        with self.assertRaisesRegex(ValueError, "frozen execution"):
            qualify_report(report, self.root)

    def test_raw_return_is_not_a_genuine_study_resumption(self):
        report = {"layouts": [{
            "rows": [{"question_id": "Q_STUDY", "pre_action_native_cycle": {
                "resumed_thread_id": "T_OLD", "foreground_changed": True,
                "selected_question_id": "Q_OLD", "priority_change_supported_by_new_evidence": False,
                "study_question_telemetry": [{"resumption_opportunity": True, "selected": False}],
            }}],
            "prior_genuine_resumption_count": 5,
            "final_metadata": {"genuine_resumption_count": 5},
        }]}
        result = resumption_accounting(report)
        self.assertEqual(result["original_raw_foreground_returns"], 1)
        self.assertEqual(result["original_returns_with_new_evidence_priority_support"], 0)
        self.assertEqual(result["original_genuine_resumption_count_increase"], 0)
        self.assertEqual(result["original_raw_foreground_returns_to_study_question"], 0)
        self.assertEqual(result["original_study_question_relevance_opportunities"], 1)
        self.assertEqual(result["original_study_question_selected_after_relevance"], 0)
        self.assertEqual(result["original_returned_question_ids"], ["Q_OLD"])

    def test_qualification_refresh_preserves_execution_reports_and_runs_no_probe(self):
        row, _ = self.fixture_row()
        observation = observe_world(initial_world(1))
        contexts = self.root / "contexts"
        pair = selector_pair(observation, row["candidate"], [], contexts / "seed-1/selector-01")
        row.update({"step": 1, "question_id": "Q_STUDY", "selector_pair": pair,
                    "pre_action_native_cycle": {"selected_question_id": "Q_OTHER"},
                    "repetitions": {arm: repeat_measures([], observation, row["candidate"], pair[arm])
                                    for arm in ("retained", "ablated")}})
        base = self.root / "base.json"
        base.write_text(json.dumps({"layouts": [{"seed": 1, "rows": [row]}]}))
        execution = self.root / "executed.py"
        execution.write_text("# exact prior execution snapshot\n")
        raw = self.root / "raw.json"
        raw.write_text(json.dumps({"original_report_sha256": file_digest(base),
                                   "followup_script_sha256": file_digest(execution), "summary": {}}))
        before = (file_digest(base), file_digest(raw))
        with patch("challenge_retained_evidence_followup.production_pair", side_effect=AssertionError("no execution during reporting")):
            result = refresh_qualifications(base, raw, execution, contexts, self.root / "reviewed.json")
        self.assertEqual((file_digest(base), file_digest(raw)), before)
        self.assertEqual(result["reporting_provenance"]["additional_native_cycles"], 0)
        self.assertEqual(result["reporting_provenance"]["execution_script_sha256"], file_digest(execution))
        self.assertEqual(result["reporting_provenance"]["raw_production_report_sha256"], before[1])
        execution.write_text("# incorrect snapshot\n")
        with self.assertRaisesRegex(ValueError, "execution source snapshot"):
            refresh_qualifications(base, raw, execution, contexts, self.root / "invalid.json")

    def test_wrong_preprobe_hash_rejected_before_mutation(self):
        source = self.root / "state.json"
        source.write_text('{}')
        before = file_digest(source)
        with self.assertRaisesRegex(ValueError, "original byte hash"):
            production_pair(source, {"native_outcome_pair": {"pre_intervention_state_sha256": "0" * 64}}, self.root / "forks")
        self.assertEqual(file_digest(source), before)
        self.assertFalse((self.root / "forks").exists())

    def test_production_flag_pair_uses_exact_input_and_valid_withheld_outcome(self):
        source = StateStore(self.root / "source/ora.json")
        observation = {"branch": "test", "baseline_fingerprint": "stable", "tracked_files": 10,
                       "python_files": 2, "python_source_lines": 100, "test_files": 1, "working_tree_clean": True}
        with fixed_clock(fixed_time(1, 0)):
            source.save(initial_state())
            AgentCore(source).cycle(observation=observation, _now_override=fixed_time(1, 0))
            recorder_store = StateStore(self.root / "recorder/recorder.json")
            recorder_store.save(initial_state())
            world, _ = _stream_prefix(recorder_store, 1)
            recorder = ChallengeShadowRecorder(recorder_store, enabled=True)
            publication = recorder.publication()
            staged = stage_publication_inquiry(AgentCore(source), policy=observe_and_inquire_policy(),
                                               source_manifest=source_manifest(), publication=publication)
        candidate = publication["selected_temporal_candidate"]
        pair = selector_pair(recorder.latest_observation(), candidate, recorder.action_associations(), self.root / "contexts")
        advanced, receipt = transition(world, pair["retained"]["command"], cycle=601)
        payload = single_transition_outcome(before=observe_world(world), after=observe_world(advanced), candidate=candidate)
        experiment_id = staged["inquiry_result"]["experiment"]["id"]
        question_id = staged["inquiry_result"]["question"]["id"]
        # Reuse the actual stored baseline observation, as the real harness does.
        observed = deepcopy(source.load()["environment_snapshots"][-1])
        original_pair = native_outcome_pair(source.path, experiment_id, question_id, payload, observed,
                                           self.root / "default-forks", fixed_time(1, 1), _agenda_identity(source.load()))
        row = {"step": 1, "candidate": candidate, "receipt": receipt, "outcome": original_pair["outcome"],
               "native_outcome_pair": original_pair, "experiment_id": experiment_id, "question_id": question_id}
        before = file_digest(source.path)
        result = production_pair(source.path, row, self.root / "production-forks")
        self.assertEqual(file_digest(source.path), before)
        self.assertTrue(result["original_pre_probe_hash_verified"])
        self.assertEqual(result["retained"]["flags"], PRODUCTION_FLAGS)
        self.assertEqual(result["withheld"]["flags"], PRODUCTION_FLAGS)
        self.assertEqual(result["retained"]["cycle"], result["withheld"]["cycle"])
        self.assertIsNotNone(result["retained"]["planning_lab_result"])
        self.assertIsNotNone(result["withheld"]["planning_lab_result"])
        self.assertEqual(result["retained"]["phase42_mismatch_count"], 0)
        self.assertEqual(result["withheld"]["phase42_mismatch_count"], 0)
        withheld = StateStore(self.root / "production-forks/withheld/ora.json").load()
        pending = next(exp for exp in withheld["experiments"] if exp["id"] == experiment_id)
        self.assertEqual(pending["readiness"], "awaiting_native_evidence")
        self.assertFalse(any(ep.get("kind") == "native_inquiry_evidence" and json.loads(ep["content"]) == payload
                             for ep in withheld["episodes"]))


if __name__ == "__main__":
    unittest.main()
