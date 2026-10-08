"""Pure synthetic validations; no original Ora actions or scientific data."""
import json
import hashlib
import unittest
from ora2.action_effect_transfer import StudyInvalid, evaluate, predict, validate_rows


def row(before, action, after, n, blocked=False):
    return {"before":list(before),"after":list(after),"action":action,
            "blocked":blocked,"source":"synthetic","source_id":f"S{n}",
            "cycle":n,"world_version":"bounded-stateful-world-v1"}


class ActionEffectTransferTests(unittest.TestCase):
    def test_opaque_action_effect_is_learned_not_named(self):
        training=validate_rows([row((0,0),"violet",(0,-1),1),
                                row((1,0),"violet",(1,-1),2)])
        d=predict(training,(2,0),"violet",model="shared_effect")
        self.assertGreater(d[(2,-1)],0.9)
        self.assertLess(d[(0,-1)],0.01)
        self.assertEqual(len(d),25)
        self.assertAlmostEqual(sum(d.values()),1.0)

    def test_public_boundaries_not_preencoded_action_mapping(self):
        training=validate_rows([row((0,0),"amber",(-1,0),1)])
        d=predict(training,(-2,0),"amber",model="shared_effect")
        self.assertGreater(d[(-2,0)],0.9)

    def test_unobserved_action_is_uniform_not_invented(self):
        training=validate_rows([row((0,0),"other",(1,0),1)])
        for model in ("shared_effect","nonspatial"):
            d=predict(training,(2,2),"unknown",model=model)
            self.assertEqual(set(d.values()),{1/25})

    def test_every_heldout_source_position_is_excluded(self):
        rows=[row((0,0),"x",(0,1),1),row((1,0),"x",(1,1),2),
              row((0,0),"x",(-1,0),3),row((1,1),"x",(1,2),4)]
        result=evaluate(rows)
        case=next(x for x in result["cases"] if x["before"]==[0,0])
        self.assertEqual(case["train_rows"],2)
        self.assertEqual(case["source_id"],"S1")
        self.assertGreater(case["shared_effect_probability"],0.9)

    def test_rename_all_commands_preserves_summary(self):
        rows=[row((0,0),"e",(0,-1),1),row((1,0),"e",(1,-1),2),
              row((2,0),"e",(2,-1),3),row((0,0),"n",(1,0),4),
              row((1,0),"n",(2,0),5),row((2,0),"n",(2,0),6,True)]
        original=evaluate(rows)
        aliases=evaluate([{**r,"action":{"e":"crochet","n":"violet"}[r["action"]]} for r in rows])
        self.assertEqual(original["mean_advantage_bits_per_case"],
                         aliases["mean_advantage_bits_per_case"])
        self.assertEqual(original["fold_wins"],aliases["fold_wins"])

    def test_repeated_identical_experiences_are_kept(self):
        training=validate_rows([row((0,0),"a",(0,-1),1),
                                row((0,0),"a",(0,-1),2),
                                row((1,0),"a",(1,-1),3)])
        self.assertGreater(predict(training,(2,0),"a",model="shared_effect")[(2,-1)],0.9)

    def test_conflicting_effects_retain_uncertainty_without_hidden_answer(self):
        training=validate_rows([row((0,0),"c",(1,0),1),
                                row((0,0),"c",(0,1),2)])
        d=predict(training,(1,1),"c",model="shared_effect")
        self.assertGreater(d[(2,1)],0.40)
        self.assertGreater(d[(1,2)],0.40)
        self.assertLess(d[(2,1)],0.6)
        self.assertAlmostEqual(sum(d.values()),1.0)

    def test_corrupt_world_identity_and_duplicate_provenance_fail_closed(self):
        good=row((0,0),"x",(0,1),1)
        with self.assertRaisesRegex(StudyInvalid,"nonmatching"):
            validate_rows([{**good,"world_version":"different"}])
        with self.assertRaisesRegex(StudyInvalid,"duplicate"):
            validate_rows([good,good])
        with self.assertRaisesRegex(StudyInvalid,"blocked"):
            validate_rows([row((0,0),"x",(0,1),1,True)])

    def test_case_probabilities_and_losses_are_finite(self):
        rows=[row((0,0),"v",(0,-1),1),row((1,0),"v",(1,-1),2),
              row((2,0),"v",(2,-1),3)]
        receipt=evaluate(rows)
        self.assertEqual(receipt["evaluated_cases"],3)
        for case in receipt["cases"]:
            self.assertGreater(case["shared_effect_probability"],0)
            self.assertGreater(case["nonspatial_probability"],0)
            self.assertEqual(case["train_rows"],2)
            self.assertEqual(case["shared_effect_loss_bits"] >= 0,True)


if __name__=="__main__":
    unittest.main()
