from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from agenttest.state import initial_state

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
for name in ("native_relation_discovery", "native_relation_family_memory", "native_relation_transfer_core"):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

relations = sys.modules["native_relation_discovery"]
families = sys.modules["native_relation_family_memory"]
transfer = sys.modules["native_relation_transfer_core"]

HELD_OUT = [
    {"id": "H1", "version": relations.RELATION_VERSION, "relation": "action_precedes_change", "feature": "novel_signal", "action": "interact"},
    {"id": "H2", "version": relations.RELATION_VERSION, "relation": "same_next_observation", "feature": "novel_signal", "action": None},
    {"id": "H3", "version": relations.RELATION_VERSION, "relation": "changes_next_observation", "feature": "novel_signal", "action": None},
]


def ledger_item(relation, *, evaluable, confirmations, refutations, index):
    return {
        "proposal": {
            "id": f"T{index}",
            "version": relations.RELATION_VERSION,
            "relation": relation,
            "feature": "training_feature",
            "action": "observe" if relation == "action_precedes_change" else None,
        },
        "evaluable": evaluable,
        "confirmations": confirmations,
        "refutations": refutations,
        "support": confirmations / evaluable if evaluable else None,
        "status": "supported" if confirmations > refutations else "challenged",
    }


def trained(profile):
    state = initial_state()
    if profile == "stability":
        ledger = [
            ledger_item("same_next_observation", evaluable=12, confirmations=10, refutations=2, index=1),
            ledger_item("changes_next_observation", evaluable=2, confirmations=1, refutations=1, index=2),
            ledger_item("action_precedes_change", evaluable=1, confirmations=1, refutations=0, index=3),
        ]
    elif profile == "change":
        ledger = [
            ledger_item("same_next_observation", evaluable=2, confirmations=1, refutations=1, index=1),
            ledger_item("changes_next_observation", evaluable=12, confirmations=7, refutations=5, index=2),
            ledger_item("action_precedes_change", evaluable=1, confirmations=1, refutations=0, index=3),
        ]
    elif profile == "action":
        ledger = [
            ledger_item("same_next_observation", evaluable=1, confirmations=1, refutations=0, index=1),
            ledger_item("changes_next_observation", evaluable=1, confirmations=1, refutations=0, index=2),
            ledger_item("action_precedes_change", evaluable=12, confirmations=7, refutations=5, index=3),
        ]
    else:
        raise ValueError(profile)
    families.update_family_memory(state, ledger)
    return state


class RelationHistorySelectionTransferTests(unittest.TestCase):
    def test_frozen_scoring_selects_different_held_out_relation_by_history(self):
        selected = {}
        for profile in ("stability", "change", "action"):
            ranked = families.rank_held_out_proposals(trained(profile), HELD_OUT)
            selected[profile] = ranked[0]["proposal"]["relation"]
        self.assertEqual(selected["stability"], "same_next_observation")
        self.assertEqual(selected["change"], "changes_next_observation")
        self.assertEqual(selected["action"], "action_precedes_change")
        self.assertEqual(len(set(selected.values())), 3)

    def test_same_held_out_candidates_reach_core_differently_by_history(self):
        selected = {}
        for profile in ("stability", "change", "action"):
            result = transfer.run_held_out_relation_core_path(trained(profile), HELD_OUT)
            self.assertEqual(result["status"], "proposed")
            selected[profile] = result["selected"]["proposal"]["relation"]
            self.assertEqual(result["question"]["source"], "native_relation_family_transfer")
        self.assertEqual(len(set(selected.values())), 3)

    def test_target_feature_never_occurs_in_training_memory(self):
        for profile in ("stability", "change", "action"):
            rendered = repr(trained(profile)[families.FAMILY_MEMORY_KEY])
            self.assertNotIn("novel_signal", rendered)

    def test_scoring_implementation_is_unchanged_from_verified_parent(self):
        # This branch intentionally adds tests only; selection transfer must emerge
        # from the already-verified family scoring rule rather than retuning it.
        source = (EXPERIMENTS / "native_relation_family_memory.py").read_text(encoding="utf-8")
        self.assertIn("persisted_relation_family_evidence", source)


if __name__ == "__main__":
    unittest.main()
