from __future__ import annotations
import ast
from dataclasses import replace
import json
import math
from pathlib import Path
import unittest

from ora2.learner import Agent, Config, CapacityError, ProtocolError, canonical


class LearnerTests(unittest.TestCase):
    def test_materialized_json_and_canonical_key_order(self):
        self.assertEqual(canonical({'b': [1, None], 'a': 2}), canonical({'a': 2, 'b': [1, None]}))
        self.assertNotEqual(canonical({}), canonical({'x': None}))

    def test_nonfinite_callback_tuple_and_nonstring_keys_rejected(self):
        for x in (float('nan'), float('inf'), lambda: 1, (1, 2), {1: 'x'}, object()):
            with self.subTest(value=repr(x)), self.assertRaises(ProtocolError):
                Agent(x)

    def test_depth_and_byte_limits(self):
        value = None
        for _ in range(15):
            value = [value]
        with self.assertRaises(ProtocolError):
            Agent(value)
        with self.assertRaises(CapacityError):
            Agent('x' * 3000)

    def test_config_strict_types_and_ranges(self):
        for values in ({'max_depth': True}, {'max_depth': 9}, {'exploration': float('nan')},
                       {'max_steps': 0}, {'progress_window': 1}, {'exploration': False}):
            with self.subTest(values=values), self.assertRaises(ProtocolError):
                Config(**values)
        with self.assertRaises(ProtocolError):
            Agent(0, config={})

    def test_forecast_normalizes_and_reserves_unseen_outcome(self):
        agent = Agent({'opaque': 'a'})
        prediction = agent.predict('arbitrary')
        self.assertAlmostEqual(sum(p for _, p in prediction.known) + prediction.unseen, 1)
        self.assertGreater(prediction.unseen, 0)
        self.assertNotIn(canonical('future'), dict(prediction.known))

    def test_no_action_execution_method_or_environment_import(self):
        path = Path(__file__).parents[1] / 'ora2' / 'learner.py'
        root = ast.parse(path.read_text())
        imports = {n.module for n in ast.walk(root) if isinstance(n, ast.ImportFrom)}
        imports |= {a.name for n in ast.walk(root) if isinstance(n, ast.Import) for a in n.names}
        forbidden = ('agenttest', 'experiments', 'socket', 'subprocess', 'requests', 'urllib', 'sqlite3', 'os')
        self.assertFalse(any(name and name.startswith(forbidden) for name in imports))
        calls = {n.func.id for n in ast.walk(root) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertFalse(calls & {'open', 'eval', 'exec', '__import__'})

    def test_empty_and_duplicate_menus_rejected_without_draw(self):
        a, b = Agent(0, seed=1), Agent(0, seed=1)
        for menu in ([], ['a', 'a'], [''], [1]):
            with self.subTest(menu=menu), self.assertRaises(ProtocolError):
                a.choose(menu)
        self.assertEqual(a.choose(['a', 'b']), b.choose(['a', 'b']))

    def test_one_outstanding_choice(self):
        agent = Agent(0)
        choice = agent.choose(['a'])
        with self.assertRaises(ProtocolError):
            agent.choose(['b'])
        agent.observe(choice, 1)
        self.assertEqual(agent.choose(['b']).step, 2)

    def test_foreign_or_changed_choice_rejected(self):
        agent = Agent(0)
        choice = agent.choose(['a', 'b'])
        before = agent.summary()
        with self.assertRaises(ProtocolError):
            agent.observe(replace(choice, action='wrong'), 1)
        self.assertEqual(before, agent.summary())

    def test_duplicate_outcome_is_not_more_evidence(self):
        agent = Agent(0)
        choice = agent.choose(['a'])
        agent.observe(choice, 1)
        before = agent.summary()
        with self.assertRaises(ProtocolError):
            agent.observe(choice, 1)
        self.assertEqual(before, agent.summary())

    def test_actual_outcome_scored_before_update(self):
        agent = Agent(0)
        choice = agent.choose(['a'])
        probability = choice.forecast.probability(canonical(1))
        event = agent.observe(choice, 1)
        self.assertEqual(event['probability_assigned_before_outcome'], probability)
        self.assertAlmostEqual(event['predictive_loss_bits'], -math.log2(probability))
        self.assertNotIn(canonical(1), dict(choice.forecast.known))
        self.assertIn(canonical(1), dict(agent.predict('a').known))

    def test_input_mutation_does_not_rewrite_experience(self):
        initial, after = {'a': [1]}, {'a': [2]}
        agent = Agent(initial)
        initial['a'].append(9)
        event = agent.observe(agent.choose(['x']), after)
        after['a'].append(9)
        self.assertEqual(event['before'], {'a': [1]})
        self.assertEqual(event['after'], {'a': [2]})

    def test_new_safe_control_is_not_blocked_by_missing_old_examples(self):
        agent = Agent('unknown')
        choice = agent.choose(['new_control'])
        self.assertEqual(choice.action, 'new_control')
        self.assertEqual(choice.reason, 'untried_control')

    def test_symbol_capacity_preserves_pending_and_prior_model(self):
        agent = Agent(0, config=Config(max_symbols=2))
        agent.observe(agent.choose(['x']), 1)
        choice = agent.choose(['x'])
        before = agent.summary()
        with self.assertRaises(CapacityError):
            agent.observe(choice, 2)
        self.assertEqual(before, agent.summary())

    def test_context_capacity_fails_before_mutation(self):
        agent = Agent(0, config=Config(max_contexts=1))
        choice = agent.choose(['x'])
        before = agent.summary()
        with self.assertRaises(CapacityError):
            agent.observe(choice, 1)
        self.assertEqual(before, agent.summary())

    def test_step_and_action_caps_do_not_reset_history(self):
        agent = Agent(0, config=Config(max_steps=1, max_actions=1))
        with self.assertRaises(CapacityError):
            agent.choose(['a', 'b'])
        agent.observe(agent.choose(['a']), 0)
        with self.assertRaises(CapacityError):
            agent.choose(['a'])
        self.assertEqual(agent.steps, 1)

    def test_opaque_action_renaming_preserves_selected_indices(self):
        a, b = Agent(0, seed=7), Agent(0, seed=7)
        menus = (['red', 'blue'], ['qq', 'zz'])
        for i in range(20):
            ca, cb = a.choose(menus[0]), b.choose(menus[1])
            self.assertEqual(menus[0].index(ca.action), menus[1].index(cb.action))
            a.observe(ca, i % 2)
            b.observe(cb, i % 2)

    def test_stable_prediction_is_learned_without_a_movement_model(self):
        agent = Agent({'sound': 'a'}, config=Config(max_depth=0))
        losses = []
        for _ in range(30):
            losses.append(agent.observe(agent.choose(['listen']), {'sound': 'a'})['predictive_loss_bits'])
        self.assertLess(losses[-1], losses[0])

    def test_seeded_choices_are_repeatable(self):
        a, b = Agent(0, seed=11), Agent(0, seed=11)
        for i in range(30):
            ca, cb = a.choose(['a', 'b']), b.choose(['a', 'b'])
            self.assertEqual(ca, cb)
            self.assertEqual(a.observe(ca, i % 3), b.observe(cb, i % 3))

    def test_forecasts_remain_finite_through_contradictory_outcomes(self):
        agent = Agent(0)
        for i in range(100):
            choice = agent.choose(['a'])
            event = agent.observe(choice, i % 7)
            self.assertTrue(math.isfinite(event['predictive_loss_bits']))
            forecast = agent.predict('a')
            self.assertAlmostEqual(sum(p for _, p in forecast.known) + forecast.unseen, 1)

    def test_compact_record_does_not_repeat_entire_forecast(self):
        agent = Agent(0)
        for i in range(10):
            event = agent.observe(agent.choose(['a']), i)
        self.assertNotIn('forecast', event['choice'])
        self.assertEqual(len(event['choice']['forecast_sha256']), 64)
        self.assertIn('depth_weights', event['choice'])

    def test_learning_progress_changes_choice_distribution_not_claimed_utility(self):
        agent = Agent('one', config=Config(progress_window=2), seed=9)
        # Explicitly authored software control, not a natural-learning result.
        for action in ('a', 'b'):
            for _ in range(4):
                agent.observe(agent.choose([action]), 'one')
        pa = agent.progress('a')
        pb = agent.progress('b')
        choice = agent.choose(['a', 'b'])
        self.assertGreater(pa + pb, 0)
        self.assertAlmostEqual(sum(choice.probabilities), 1)
        self.assertGreaterEqual(min(choice.probabilities), agent.config.exploration / 2)
        self.assertEqual(choice.reason, 'measured_learning_progress')


if __name__ == '__main__':
    unittest.main()
