from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from agenttest.core import AgentCore
from scripts.phase42_experiment_routing_eval import evaluate_experiment_routes
from scripts.phase42_integrity_eval import evaluate as old_integrity
from scripts.phase42_resumption_opportunity_eval import evaluate_resumption_opportunities


def route(text="What is the relationship between two concepts?", owner="Q1", intention=None):
    return {"cycle": 10, "question": {"id": "Q2", "text": text},
            "experiment": {"id": "X1", "question_id": owner},
            "intention": intention or {"id": "I1", "kind": "resolve_pending_evidence", "target": "X1"}}


class IndependentRoutingTests(unittest.TestCase):
    def status(self, record, state=None):
        return evaluate_experiment_routes([record], state)["records"][0]["status"]

    def test_corruption_rejected_even_with_green_old_checks_and_false_telemetry(self):
        state = {"agenda": {"decisions": []}}
        self.assertTrue(old_integrity(state)["ok"])
        self.assertEqual(evaluate_resumption_opportunities(state)["handoff_or_selection_mismatch_count"], 0)
        record = route()
        record["experiment_routing"] = {"relationship": "owned", "selected_question_id": "Q2", "returned_experiment_id": "X1", "experiment_question_id": "Q2"}
        result = evaluate_experiment_routes([record])
        self.assertEqual(result["status"], "routing_invalid")
        self.assertEqual(result["mismatch_count"], 1)
        self.assertEqual(result["telemetry_disagreement_count"], 1)

    def test_owned_does_not_require_intention(self):
        record = route(owner="Q2")
        del record["intention"]
        self.assertEqual(self.status(record), "owned")

    def test_pending_and_specification_followups_are_independently_parsed(self):
        examples = [
            ("resolve_pending_evidence", "What obtainable evidence would resolve pending experiment X1 with the least additional assumption?"),
            ("specify_experiment", "What observable, evidence source, and resolution rule would make experiment X1 evidence-ready?"),
        ]
        # A poisoned production helper must not affect either independent result.
        with patch.object(AgentCore, "_experiment_question_relationship", side_effect=AssertionError("validator called production helper")):
            for kind, text in examples:
                for varied in (text, "  " + text.upper().replace(" ", "  ") + "  "):
                    with self.subTest(kind=kind, text=varied):
                        self.assertEqual(self.status(route(varied, intention={"id": "I1", "kind": kind, "target": "X1"})), "explicit_followup")

    def test_wrong_target_kind_and_near_match_are_mismatches(self):
        valid = "What obtainable evidence would resolve pending experiment X1 with the least additional assumption?"
        for record in (
            route(valid.replace("X1", "X2")),
            route(valid, intention={"kind": "specify_experiment", "target": "X1"}),
            route(valid, intention={"kind": "resolve_pending_evidence", "target": "X2"}),
            route(valid + " Also consider X1."),
            route("What else might experiment X1 tell us?"),
        ):
            with self.subTest(record=record):
                self.assertEqual(self.status(record), "mismatch")

    def test_followup_missing_intention_is_unknown(self):
        record = route("What obtainable evidence would resolve pending experiment X1 with the least additional assumption?")
        del record["intention"]
        self.assertEqual(self.status(record), "unknown")

    def test_unrelated_route_is_rejected_without_intention_history(self):
        state = {"cycles": 10, "questions": [{"id": "Q2", "text": "unrelated"}], "experiments": [{"id": "X1", "question_id": "Q1"}]}
        record = {"cycle": 10, "selected_question_id": "Q2", "experiment_id": "X1", "intention_id": "I_MISSING"}
        self.assertEqual(self.status(record, state), "mismatch")

    def test_invalid_snapshot_and_duplicate_embedded_followup_intention(self):
        with self.assertRaises(ValueError):
            evaluate_experiment_routes([route()], [])
        record = route("What obtainable evidence would resolve pending experiment X1 with the least additional assumption?")
        state = {"cycles": 10, "questions": [record["question"]], "experiments": [record["experiment"]], "intentions": [record["intention"], deepcopy(record["intention"])]}
        self.assertEqual(self.status(record, state), "unknown")

    def test_null_absent_and_missing_records_are_distinct(self):
        record = route()
        record["experiment"] = None
        self.assertEqual(self.status(record), "no_experiment")
        del record["experiment"]
        self.assertEqual(self.status(record), "unchecked")
        record["experiment_id"] = "X_GONE"
        self.assertEqual(self.status(record), "unknown")
        record["experiment"] = {"id": "X_GONE"}
        self.assertEqual(self.status(record), "unknown")

    def test_matching_snapshot_resolves_journal_ids_only_at_its_cycle(self):
        record = {"cycle": 10, "selected_question_id": "Q2", "experiment_id": "X1"}
        state = {"cycles": 10, "questions": [{"id": "Q2", "text": "unrelated"}], "experiments": [{"id": "X1", "question_id": "Q2"}]}
        self.assertEqual(self.status(record, state), "owned")
        state["cycles"] = 11
        self.assertEqual(self.status(record, state), "unknown")
        state["cycles"] = True
        self.assertEqual(self.status(record, state), "unknown")

    def test_missing_duplicate_and_contradictory_snapshot_records_are_unknown(self):
        record = route(owner="Q2")
        state = {"cycles": 10, "questions": [deepcopy(record["question"])], "experiments": [deepcopy(record["experiment"])]}
        for collection in ("questions", "experiments"):
            for missing in (False, True):
                corrupted = deepcopy(state)
                corrupted[collection] = [] if missing else corrupted[collection] * 2
                self.assertEqual(self.status(record, corrupted), "unknown")
        state["experiments"][0]["question_id"] = "Q1"
        result = evaluate_experiment_routes([record], state)
        self.assertEqual(result["raw_contradiction_count"], 1)
        self.assertEqual(result["status"], "routing_invalid")

    def test_journal_pending_and_specification_followups(self):
        for kind, text in [
            ("resolve_pending_evidence", "What obtainable evidence would resolve pending experiment X1 with the least additional assumption?"),
            ("specify_experiment", "What observable, evidence source, and resolution rule would make experiment X1 evidence-ready?"),
        ]:
            state = {"cycles": 10, "questions": [{"id": "Q2", "text": text}], "experiments": [{"id": "X1", "question_id": "Q1"}], "intentions": [{"id": "I1", "kind": kind, "target": "X1"}]}
            record = {"cycle": 10, "selected_question_id": "Q2", "experiment_id": "X1", "intention_id": "I1"}
            self.assertEqual(self.status(record, state), "explicit_followup")
            state["intentions"] *= 2
            self.assertEqual(self.status(record, state), "unknown")

    def test_raw_ids_contradicting_embedded_records_do_not_choose_a_winner(self):
        for field, value in (("selected_question_id", "Q_OTHER"), ("experiment_id", "X_OTHER")):
            record = route()
            record[field] = value
            result = evaluate_experiment_routes([record])
            self.assertEqual(result["unknown_count"], 1)
            self.assertEqual(result["raw_contradiction_count"], 1)

    def test_telemetry_cannot_override_valid_ownership_or_null(self):
        record = route(owner="Q2")
        record["experiment_routing"] = {"relationship": "unrelated"}
        result = evaluate_experiment_routes([record])
        self.assertEqual(result["owned_count"], 1)
        self.assertEqual(result["telemetry_disagreement_count"], 1)
        record["experiment"] = None
        record["experiment_routing"] = {"returned_experiment_id": "X1"}
        self.assertEqual(evaluate_experiment_routes([record])["telemetry_disagreement_count"], 1)

    def test_counts_no_checked_routes_and_readonly_inputs(self):
        records = [route(owner="Q2"), {"cycle": 9}, {"cycle": 10, "selected_question_id": "Q2", "experiment_id": "X_MISSING"}]
        before = deepcopy(records)
        result = evaluate_experiment_routes(records)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["checked_count"], 1)
        self.assertEqual((result["unknown_count"], result["unchecked_count"]), (1, 1))
        self.assertEqual(records, before)
        self.assertEqual(evaluate_experiment_routes([])["status"], "not_checked")

    def test_cli_exit_statuses_and_jsonl(self):
        script = Path(__file__).resolve().parents[1] / "scripts/phase42_experiment_routing_eval.py"
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/"records.jsonl"
            for records, code in [([route(owner="Q2")], 0), ([route()], 1), ([{"cycle": 10}], 2)]:
                file.write_text("\n".join(json.dumps(r) for r in records))
                process = subprocess.run([sys.executable, str(script), "--records", str(file)], capture_output=True, text=True)
                self.assertEqual(process.returncode, code, process.stderr)
                self.assertIn("checked_count", json.loads(process.stdout))


if __name__ == "__main__":
    unittest.main()
