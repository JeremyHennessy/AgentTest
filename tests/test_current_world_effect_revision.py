"""Focused promotion-unit controls; no real admission or world transition."""
from copy import deepcopy
import unittest

from agenttest import current_world_investigation as investigation
from agenttest.grounded_policy import policy
from agenttest.grounded_policy.primitives import canonical, digest


def row(identifier, before, after, action="north"):
    return {"event_id": identifier,
            "before_context": {"position": before, "inventory_ids": None, "visible_ids": None},
            "action": action, "after_position": after,
            "refs": {"before": digest(before), "receipt": digest(identifier), "after": digest(after)}}


class CurrentWorldEffectRevision(unittest.TestCase):
    def test_familiar_effect_does_not_spend_slot_and_all_new_effects_keep_full_rows(self):
        discovery = [row("original", [0, 0], [1, 0])]
        familiar = row("familiar-new-position", [1, 0], [2, 0])
        zero = row("new-zero", [2, 0], [2, 0])
        contradictory = row("new-contradictory", [0, 1], [-1, 1])
        repeated_zero = row("zero-new-position", [1, 1], [1, 1])
        rows = discovery + [familiar, zero, contradictory, repeated_zero]
        before = canonical(rows)
        promoted = investigation._promotions(discovery, rows)
        self.assertEqual(promoted, [zero, contradictory])
        self.assertEqual(canonical(rows), before)
        self.assertEqual(promoted[0]["before_context"]["position"], [2, 0])
        self.assertEqual(promoted[1]["refs"], contradictory["refs"])
        cohort = policy.build_cohort(discovery + promoted)
        self.assertEqual(cohort["actions"][0]["status"], "outside_first_model_class")
        self.assertEqual(investigation.REVISION_VERSION, "observed-effect-revision-v1")
        self.assertEqual(investigation.VERSION, "current-world-investigation-v3")

    def test_historical_context_revision_and_original_case_keep_their_exact_recipe(self):
        original = row("original", [0, 0], [1, 0])
        rows = [original,
                row("old-context-1", [1, 0], [2, 0]),
                row("old-context-2", [2, 0], [2, 0]),
                row("old-context-3", [0, 1], [-1, 1]),
                row("old-context-4", [1, 1], [1, 1]),
                row("evidence-only", [0, 0], [1, 0])]
        # Independently specified historical context additions, not the new unit.
        old_discovery = rows[:5]
        base = policy.build_cohort([original])
        old_cohort = policy.build_cohort(old_discovery)
        revision = {"revision_id": "CWR000001", "version": "observed-transition-revision-v1",
                    "created_cycle": 10, "request_id": "old:recipe",
                    "parent_discovery_hash": digest([original]), "parent_cohort_hash": base["cohort_digest"],
                    "source_row_count": len(rows), "source_rows_hash": digest(investigation._refs(rows)),
                    "promoted_refs": investigation._refs(rows[1:5]), "discovery": old_discovery,
                    "cohort": old_cohort,
                    "structural_changes": [{"action": "north", "before_status": "insufficient_explanatory_diversity",
                        "after_status": "outside_first_model_class", "added_structures": [], "removed_structures": []}]}
        revision["revision_hash"] = digest(revision)
        lane = {"version": "current-world-investigation-v2", "discovery": [original], "cohort": base,
                "discovery_revisions": [revision], "active_discovery_revision_id": revision["revision_id"]}
        original_case = {"discovery_hash": digest([original]),
                         "decision": policy.evaluate(base, original["before_context"], rows[1:])}
        revised_case = {"discovery_revision_id": revision["revision_id"],
                        "discovery_revision_hash": revision["revision_hash"],
                        "discovery_hash": digest(old_discovery),
                        "decision": policy.evaluate(old_cohort, original["before_context"], rows[5:])}
        frozen = canonical([lane, original_case, revised_case])
        d, _, evidence = investigation.discovery_partition(lane, {"rows": rows}, revised_case)
        self.assertEqual(d, old_discovery)
        self.assertEqual(evidence, rows[5:])
        d0, _, old_evidence = investigation.discovery_partition(lane, {"rows": rows}, original_case)
        self.assertEqual(d0, [original])
        self.assertEqual(old_evidence, rows[1:])
        self.assertEqual(canonical([lane, original_case, revised_case]), frozen)
        self.assertEqual(investigation._promotions([original], rows), [rows[2], rows[3]])
        self.assertNotEqual(investigation.REVISION_VERSION, revision["version"])

    def test_effect_promotion_retains_source_order_and_same32_limit(self):
        original = row("original", [0, 0], [1, 0])
        rows = [original]
        for action in ("north", "east"):
            for x in range(-2, 3):
                for y in range(-2, 3):
                    rows.append(row(f"reverse-{100-len(rows):03d}", [-2, -2], [x, y], action))
        expected = [record for record in rows[1:]
                    if not (record["action"] == "north" and record["after_position"] == [-1, -2])][:32]
        self.assertEqual(investigation._promotions([original], rows), expected)
        self.assertEqual(investigation.MAX_DISCOVERY_ADDITIONS, 32)
        self.assertEqual(investigation.MAX_REVISED_DISCOVERY, 64)
        self.assertEqual(investigation.MAX_CASES, 2)
        self.assertEqual(investigation.ACTION_ALLOWANCE, 2)


if __name__ == "__main__":
    unittest.main()
