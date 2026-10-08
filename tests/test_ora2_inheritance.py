import copy
import unittest
from ora2.learner import Agent, Config, ProtocolError, CapacityError
from ora2.baseline import project, seeded_agent, public_observation, WORLD


def fixture():
    rows = []
    for i in range(12):
        before = [i % 2, 0]
        after = [(i + 1) % 2, 0]
        rows.append({'source': 'authored_fixture', 'source_id': str(i), 'cycle': i + 1,
                     'before': before, 'after': after, 'action': 'north',
                     'delta': [after[0] - before[0], 0], 'blocked': False, 'world_version': WORLD})
    return {'schema_version': 24, 'cycles': 12,
            'identity': {'designation': 'authored-fixture', 'chosen_name': 'Ora fixture, not historical Ora'},
            'planning_lab': {'world_version': WORLD, 'bounds': 2, 'position': [0, 0],
                             'transition_observations': rows}}


class InheritanceTests(unittest.TestCase):
    def test_inherited_action_does_not_draw_rng_or_claim_choice(self):
        a = Agent(0, seed=9)
        before = a._random.getstate()
        event = a.inherit(0, 'test', 1)
        self.assertEqual(a._random.getstate(), before)
        self.assertEqual(event['choice']['reason'], 'inherited_observation_not_agent_choice')
        self.assertEqual(a.steps, 1)

    def test_inherited_stream_and_exposure_predictions_match(self):
        a, b = Agent(0), Agent(0)
        for i in range(20):
            action, after = ('a' if i % 2 else 'b'), (i + 1) % 3
            before = i % 3
            event = a.inherit(before, action, after)
            other = b.observe(b.choose([action]), after)
            self.assertEqual(event['predictive_loss_bits'], other['predictive_loss_bits'])
            self.assertEqual(a.predict(action), b.predict(action))

    def test_sequence_break_does_not_invent_a_transition(self):
        a = Agent(0)
        a.inherit(0, 'a', 1)
        a.inherit(7, 'b', 8, sequence_break=True)
        self.assertEqual(a.steps, 2)
        self.assertEqual(a.observation, '8')
        self.assertEqual(len(a._history), 1)
        self.assertEqual(a._action_counts, {'a': 1, 'b': 1})

    def test_discontinuity_and_pending_reject(self):
        a = Agent(0)
        with self.assertRaises(ProtocolError):
            a.inherit(1, 'a', 2)
        c = a.choose(['a'])
        with self.assertRaises(ProtocolError):
            a.inherit(0, 'a', 1)
        self.assertEqual(a._pending, c)

    def test_failed_inheritance_keeps_model_and_sequence(self):
        a = Agent(0, config=Config(max_contexts=1))
        before = copy.deepcopy(a.__dict__)
        with self.assertRaises(CapacityError):
            a.inherit(2, 'a', 3, sequence_break=True)
        self.assertEqual(a.observation, before['observation'])
        self.assertEqual(a._symbols, before['_symbols'])
        self.assertEqual(a._tables, before['_tables'])
        self.assertEqual(a.steps, 0)
        self.assertIsNone(a._pending)

    def test_every_unique_row_is_inherited_without_recounting(self):
        data = fixture()
        data['planning_lab']['transition_observations'].append(copy.deepcopy(data['planning_lab']['transition_observations'][-1]))
        origin = project(data)
        agent = seeded_agent(origin, seed=0, config=Config())
        self.assertEqual(agent.steps, 12)
        self.assertEqual(origin['duplicate_rows'], 1)
        self.assertEqual(agent.observation, '{"position":[0,0]}')
        self.assertGreater(len(agent._history), 0)

    def test_changed_duplicate_rejects(self):
        data = fixture()
        row = copy.deepcopy(data['planning_lab']['transition_observations'][-1])
        row['cycle'] = 11
        data['planning_lab']['transition_observations'].append(row)
        with self.assertRaises(ProtocolError):
            project(data)

    def test_other_world_is_not_blended(self):
        data = fixture()
        data['planning_lab']['transition_observations'][5]['world_version'] = 'bounded-transfer-world-v1'
        origin = project(data)
        self.assertEqual(origin['other_world_rows'], 1)
        self.assertEqual(len(origin['rows']), 11)
        self.assertTrue(origin['rows'][5]['sequence_break'])

    def test_main_starter_wrong_world_and_invalid_scalars_reject(self):
        for field, value in [('cycles', 0), ('schema_version', 25)]:
            data = fixture()
            data[field] = value
            with self.assertRaises(ProtocolError): project(data)
        for field, value in [('before', [True, 0]), ('cycle', True), ('delta', [9, 9])]:
            data = fixture()
            data['planning_lab']['transition_observations'][0][field] = value
            with self.assertRaises(ProtocolError): project(data)

    def test_projection_never_includes_goals_rewards_or_hidden_world(self):
        data = fixture()
        data['planning_lab']['secret'] = 'do not expose'
        origin = project(data)
        self.assertEqual(public_observation(origin['position']), {'position': [0, 0]})
        self.assertNotIn('secret', origin)

    def test_null_chosen_name_is_preserved_without_inventing_one(self):
        data = fixture()
        data['identity']['chosen_name'] = None
        before = copy.deepcopy(data['identity'])
        origin = project(data)
        self.assertEqual(origin['identity'], before)
        self.assertIsNone(origin['identity']['chosen_name'])

    def test_actual_early_legacy_shape_is_archived_not_assigned_positions(self):
        data = fixture()
        early = {'action': 'north', 'blocked': False, 'cycle': 0,
                 'delta': [1, 0], 'source': 'action_lab', 'source_id': 'LA000001'}
        data['planning_lab']['transition_observations'].insert(0, early)
        before = copy.deepcopy(data)
        origin = project(data)
        self.assertEqual(origin['delivered_rows'], 13)
        self.assertEqual(len(origin['rows']), 12)
        self.assertEqual(origin['unlocated_legacy_rows'], 1)
        self.assertEqual(origin['unlocated_legacy_refs'][0]['source_id'], 'LA000001')
        self.assertEqual(origin['other_world_rows'], 0)
        self.assertEqual(data, before)
        self.assertTrue(origin['rows'][0]['sequence_break'])

    def test_legacy_gap_breaks_sequence_and_does_not_count_as_new_learning(self):
        data = fixture()
        early = {'action': 'north', 'blocked': False, 'cycle': 5,
                 'delta': [1, 0], 'source': 'planning_lab', 'source_id': 'old'}
        data['planning_lab']['transition_observations'].insert(5, early)
        origin = project(data)
        self.assertTrue(origin['rows'][5]['sequence_break'])
        agent = seeded_agent(origin, seed=0, config=Config())
        self.assertEqual(agent.steps, 12)
        self.assertEqual(origin['unlocated_legacy_rows'], 1)

    def test_unknown_or_partial_shape_is_not_silently_treated_as_legacy(self):
        for changes in ({'world_version': None}, {'before': [0, 0]},
                        {'source': 'unknown'}, {'blocked': True}, {'delta': [True, 0]}):
            data = fixture()
            early = {'action': 'north', 'blocked': False, 'cycle': 0,
                     'delta': [1, 0], 'source': 'action_lab', 'source_id': 'LA000001'}
            early.update(changes)
            data['planning_lab']['transition_observations'].insert(0, early)
            with self.assertRaises(ProtocolError):
                project(data)

    def test_malformed_position_in_identified_world_still_rejects(self):
        data = fixture()
        del data['planning_lab']['transition_observations'][0]['before']
        with self.assertRaises(ProtocolError):
            project(data)
