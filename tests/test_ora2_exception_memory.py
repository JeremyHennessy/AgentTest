"""Standalone belief-revision tests, synthetic records, no world execution."""
from copy import deepcopy
import unittest

from ora2.exception_memory import propose_from_history
from ora2.action_effect_transfer import StudyInvalid


def example(before, action, after, index, *, blocked=False, world="bounded-stateful-world-v1"):
    return {"before":list(before), "action":action, "after":list(after),
            "cycle":index, "blocked":blocked, "source":"synthetic",
            "source_id":f"H{index}", "world_version":world}


def probability(offer, destination):
    return next(r["probability"] for r in offer["probabilities"] if r["after"]==list(destination))


class LearnedExceptionMemoryTests(unittest.TestCase):
    def setUp(self):
        self.prefix=[example((0,0),"violet",(1,0),1),
                     example((1,0),"violet",(2,0),2)]

    def test_global_effect_propagates_to_unseen_location(self):
        model=propose_from_history(self.prefix,(-1,0),"violet")
        self.assertEqual(model["local_observations"],0)
        self.assertGreater(probability(model,(0,0)),0.9)
        self.assertEqual(model["general_local_disagreement_bits"],0)
        self.assertFalse(model["autonomous_action_authorized"])

    def test_first_unexpected_local_outcome_increases_its_probability(self):
        prior=propose_from_history(self.prefix,(-1,0),"violet")
        learned=propose_from_history(self.prefix+
            [example((-1,0),"violet",(-1,0),3,blocked=True)],(-1,0),"violet")
        self.assertGreater(probability(learned,(-1,0)),probability(prior,(-1,0)))
        self.assertGreater(learned["general_local_disagreement_bits"],0)
        self.assertEqual(learned["local_source_refs"],
                         [{"source":"synthetic","source_id":"H3"}])

    def test_repeated_exception_strengthens_an_evidence_bound_revision(self):
        prefix=self.prefix+[example((-1,0),"violet",(-1,0),3,blocked=True)]
        one=propose_from_history(prefix,(-1,0),"violet")
        two=propose_from_history(prefix+
            [example((-1,0),"violet",(-1,0),4,blocked=True)],(-1,0),"violet")
        self.assertGreater(probability(two,(-1,0)),probability(one,(-1,0)))
        self.assertGreater(two["local_weight"],one["local_weight"])

    def test_exception_evidence_cannot_spill_into_other_locations(self):
        records=self.prefix+[example((-1,0),"violet",(-1,0),3,blocked=True)]
        model=propose_from_history(records,(0,-1),"violet")
        self.assertEqual(model["local_observations"],0)
        self.assertGreater(probability(model,(1,-1)),0.9)

    def test_contradictory_local_outcomes_remain_uncertain(self):
        records=self.prefix+[example((-1,0),"violet",(-1,0),3,blocked=True),
                             example((-1,0),"violet",(0,0),4)]
        model=propose_from_history(records,(-1,0),"violet")
        self.assertGreater(probability(model,(-1,0)),0.1)
        self.assertGreater(probability(model,(0,0)),0.1)
        self.assertLess(probability(model,(-1,0)),0.9)

    def test_cold_reconstruction_is_byte_equal_without_history_mutation(self):
        before=deepcopy(self.prefix)
        first=propose_from_history(self.prefix,(2,0),"violet")
        second=propose_from_history(deepcopy(self.prefix),(2,0),"violet")
        self.assertEqual(first,second)
        self.assertEqual(self.prefix,before)
        self.assertFalse(first["pilot_enabled"])

    def test_opaque_renaming_does_not_affect_probabilities(self):
        a=propose_from_history(self.prefix,(2,0),"violet")
        renamed=[{**x,"action":"aqua"} for x in self.prefix]
        b=propose_from_history(renamed,(2,0),"aqua")
        self.assertEqual(a["probabilities"],b["probabilities"])

    def test_mixed_worlds_and_duplicate_receipts_rejected(self):
        corrupt=self.prefix+[example((2,0),"violet",(2,1),3,world="other-world")]
        with self.assertRaisesRegex(StudyInvalid,"world"):
            propose_from_history(corrupt,(0,0),"violet")
        with self.assertRaisesRegex(StudyInvalid,"duplicate"):
            propose_from_history(self.prefix+self.prefix,(0,0),"violet")


if __name__=="__main__":
    unittest.main()
