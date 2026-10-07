"""Authored evaluation/accounting controls, not a run of the actual study."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from ora2.learner import Agent, Config, Forecast, canonical
from ora2.baseline import ACTIONS, public_observation
from studies.decision001 import run as study


class EvaluationTests(unittest.TestCase):
    def forecast(self):
        return Forecast(((study.CELL_SYMBOLS[0], .4), (study.CELL_SYMBOLS[1], .2)), .4, (1.0,))

    def test_fixed_alphabet_keeps_known_probabilities(self):
        result = study.lifted_probabilities(self.forecast())
        self.assertEqual(result[study.CELL_SYMBOLS[0]], .4)
        self.assertEqual(result[study.CELL_SYMBOLS[1]], .2)
        self.assertAlmostEqual(result[study.CELL_SYMBOLS[2]], .4/24)
        self.assertAlmostEqual(sum(result.values()) + .4/24, 1)

    def test_full_vocabulary_retains_outside_mass(self):
        forecast = Forecast(tuple((s, .96/25) for s in study.CELL_SYMBOLS), .04, (1.0,))
        result = study.lifted_probabilities(forecast)
        self.assertAlmostEqual(sum(result.values()), .96)

    def test_foreign_or_invalid_forecast_rejects(self):
        for f in (Forecast((('"not-position"', 1.0),), 0, (1.0,)),
                  Forecast(((study.CELL_SYMBOLS[0], .9),), .9, (1.0,)),
                  Forecast(((study.CELL_SYMBOLS[0], -1.0),), 2.0, (1.0,))):
            with self.assertRaises(ValueError):
                study.lifted_probabilities(f)

    def test_all_100_queries_do_not_train_draw_or_reorient_acting_model(self):
        agent = Agent(public_observation([0, 0]), seed=51)
        for i in range(4):
            choice = agent.choose(ACTIONS)
            agent.observe(choice, public_observation([0, 0]))
        before = copy.deepcopy(agent.__dict__)
        # Explicit authored stationary truths, never the repository world.
        truths = {(p, a): {'after': list(p)} for p in study.CELLS for a in ACTIONS}
        with patch.object(Agent, 'observe', side_effect=AssertionError('evaluator trained')):
            value = study.assess_without_mutation(agent, truths, set())
        self.assertEqual(len(value['cases']), 100)
        self.assertEqual({(tuple(c['position']), c['action']) for c in value['cases']}, set(truths))
        self.assertEqual(agent._tables, before['_tables'])
        self.assertEqual(agent._totals, before['_totals'])
        self.assertEqual(agent._log_weights, before['_log_weights'])
        self.assertEqual(agent._symbols, before['_symbols'])
        self.assertEqual(agent._losses, before['_losses'])
        self.assertEqual(agent._random.getstate(), before['_random'].getstate())
        self.assertEqual(agent.observation, before['observation'])

    def test_subset_is_separate_from_primary(self):
        agent = Agent(public_observation([0, 0]))
        truths = {(p, a): {'after': list(p)} for p in study.CELLS for a in ACTIONS}
        a = study.fixed_evaluation(agent, truths, set())
        b = study.fixed_evaluation(agent, truths, set(truths))
        self.assertEqual(a['loss_bits'], b['loss_bits'])
        self.assertIsNone(a['initially_underobserved_loss'])
        self.assertEqual(b['loss_bits'], b['initially_underobserved_loss'])


class DecisionRuleTests(unittest.TestCase):
    def fixture(self, diffs):
        arms = [{'arm': 'phase41', 'seed': None, 'actions': 128,
                 'checkpoints': [{'actions': 128, 'loss_bits': .5}]}]
        for seed, diff in enumerate(diffs):
            for name, loss in (('ora2', 1-diff), ('uniform', 1)):
                arms.append({'arm': name, 'seed': seed, 'actions': 128,
                             'rng_sha256': 'matching',
                             'checkpoints': [{'actions': 128, 'loss_bits': loss}]})
        return arms

    def test_both_declared_thresholds_required(self):
        self.assertTrue(study.comparison(self.fixture([.03]*16))['engineering_threshold_met'])
        self.assertFalse(study.comparison(self.fixture([.001]*16))['engineering_threshold_met'])
        self.assertFalse(study.comparison(self.fixture([.1]*11+[-.001]*5))['engineering_threshold_met'])

    def test_negative_and_ties_are_not_dropped(self):
        result = study.comparison(self.fixture([.03]*4+[-.03]*4+[0]*8))
        self.assertEqual((result['ora2_wins'], result['ora2_losses'], result['ties']), (4, 4, 8))
        self.assertEqual(len(result['pairs']), 16)
        self.assertFalse(result['engineering_threshold_met'])

    def test_missing_arm_or_seed_invalidates(self):
        arms = self.fixture([.1]*16)
        with self.assertRaises(ValueError):
            study.comparison(arms[:-1])
        with self.assertRaises(ValueError):
            study.comparison(arms[1:])

    def test_mismatched_budget_or_rng_invalidates(self):
        for field, value in (('actions', 127), ('rng_sha256', 'different')):
            arms = self.fixture([.1]*16)
            arms[1][field] = value
            with self.assertRaises(ValueError):
                study.comparison(arms)

    def test_deterministic_reference_is_not_replicated(self):
        arms = self.fixture([.1]*16)
        arms.append(copy.deepcopy(arms[0]))
        with self.assertRaises(ValueError):
            study.comparison(arms)


if __name__ == '__main__':
    unittest.main()
