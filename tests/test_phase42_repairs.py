import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from agenttest.agenda import update_agenda
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state, migrate_state
from tests.test_native_inquiry_interface import seeded_state, temporal_candidate


def question(identifier, text):
    return dict(id=identifier, text=text, status='open', created_cycle=1,
                times_selected=0, last_selected_cycle=None)


class Phase42RepairTests(unittest.TestCase):
    def test_unrelated_intention_target_is_not_reused_or_mutated(self):
        for kind, status in [('resolve_pending_evidence', 'proposed'),
                             ('specify_experiment', 'needs_specification')]:
            with self.subTest(kind=kind):
                state = initial_state()
                state['cycles'] = 20
                selected = question('Q2', 'A different inquiry')
                experiment = dict(id='X1', question_id='Q1', status=status)
                state['experiments'] = [experiment]
                before = deepcopy(experiment)
                result = AgentCore()._select_or_propose_experiment(
                    state, selected, dict(id='I1', kind=kind, target='X1'),
                    None, require_grounded=True)
                self.assertIsNone(result)
                self.assertEqual(experiment, before)

    def test_owned_and_explicit_followups_remain_valid(self):
        core = AgentCore()
        for kind, status in [('resolve_pending_evidence', 'proposed'),
                             ('specify_experiment', 'needs_specification')]:
            for owned in (False, True):
                with self.subTest(kind=kind, owned=owned):
                    state = initial_state()
                    state['cycles'] = 20
                    intention = dict(id='I1', kind=kind, target='X1')
                    text = core._generate_question(state, None, intention, None)
                    selected = question('Q1' if owned else 'Q2', text)
                    state['experiments'] = [dict(id='X1', question_id='Q1', status=status)]
                    self.assertEqual(core._select_or_propose_experiment(
                        state, selected, intention, None, require_grounded=True)['id'], 'X1')

    def test_fresh_agenda_activates_and_existing_state_is_preserved(self):
        state = initial_state()
        self.assertEqual(state['agenda']['started_cycle'], 0)
        state['cycles'] = 1
        state['questions'] = [question('Q1', 'one'), question('Q2', 'two')]
        state['questions'][1]['source'] = 'empirical_frontier_transfer'
        self.assertIsNotNone(update_agenda(state, legacy_question=state['questions'][0], cycle=1))
        before = deepcopy(state['agenda'])
        self.assertEqual(migrate_state(state)['agenda'], before)

    def test_missing_file_reload_and_null_marker_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / 'state.json')
            state = store.load()
            self.assertEqual(state['agenda']['started_cycle'], 0)
            state['cycles'] = 7
            state['agenda']['started_cycle'] = None
            state['agenda']['genuine_resumption_count'] = 5
            state['agenda']['last_genuine_resumption'] = {'id': 'prior'}
            store.save(state)
            recovered = store.load()
            self.assertEqual(recovered['agenda']['started_cycle'], 7)
            self.assertEqual(recovered['agenda']['genuine_resumption_count'], 5)
            self.assertEqual(recovered['agenda']['last_genuine_resumption'], {'id': 'prior'})
            store.save(recovered)
            self.assertEqual(store.load()['agenda'], recovered['agenda'])

    def test_schema24_cycle7_boundary_remains_prospective(self):
        state = initial_state()
        state['schema_version'] = 24
        state['cycles'] = 7
        state['agenda']['started_cycle'] = None
        state['questions'] = [question('Q1', 'one'), question('Q2', 'two')]
        state['questions'][1]['source'] = 'empirical_frontier_transfer'
        state = migrate_state(state)
        self.assertEqual(state['agenda']['started_cycle'], 7)
        self.assertIsNone(update_agenda(state, legacy_question=state['questions'][0], cycle=7))
        self.assertIsNotNone(update_agenda(state, legacy_question=state['questions'][0], cycle=8))

    def test_routing_diagnostics_distinguish_missing_unknown_and_unrelated(self):
        core = AgentCore()
        selected = question('Q2', 'A different inquiry mentioning X1')
        intention = dict(kind='resolve_pending_evidence', target='X1')
        self.assertEqual(core._experiment_question_relationship(selected, None, intention), 'no_experiment')
        self.assertEqual(core._experiment_question_relationship(selected, {'id': 'X1'}, intention), 'unknown')
        self.assertEqual(core._experiment_question_relationship(selected, {'id': 'X1', 'question_id': 'Q1'}, intention), 'unrelated')

    def test_actual_archive_reentry_counts_each_evidence_reference_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / 'state.json')
            state = initial_state()
            state['questions'] = [question(f'Q{i}', f'inquiry {i}') for i in range(6)]
            for item in state['questions']:
                item['source'] = 'empirical_frontier_transfer'
            for item in state['questions'][3:5]:
                item['status'] = 'closed'
            target = state['questions'][-1]
            target['thread_evidence_refs'] = ['E1']
            def step(legacy):
                state['cycles'] += 1
                return update_agenda(state, legacy_question=legacy, cycle=state['cycles'])
            step(target)
            identity = next(t['id'] for t in state['agenda']['threads'] if t['question_id'] == target['id'])
            for item in state['questions'][:3]:
                item['thread_evidence_refs'] = [f'{item["id"]}E{n}' for n in range(6)]
            step(state['questions'][0])  # target suspended and still bounded
            self.assertEqual(next(t['status'] for t in state['agenda']['threads'] if t['id'] == identity), 'suspended')
            # Give the remaining competitor evidence to evict target without changing weights.
            for item in state['questions'][3:5]:
                item['status'] = 'open'
                item['thread_evidence_refs'] = ['extra' + str(n) for n in range(6)]
            step(state['questions'][0])
            archived = next(t for t in state['agenda']['archived_threads'] if t['id'] == identity)
            self.assertEqual(archived['thread_progress_evidence_refs'], ['E1'])
            self.assertEqual(archived['status'], 'suspended')
            store.save(state)
            state = store.load()
            target = state['questions'][-1]
            old = step(target)
            self.assertEqual(old['selected']['new_evidence_refs'], [])
            self.assertEqual(old['selected_thread_id'], identity)
            target['thread_evidence_refs'].append('E2')
            fresh = step(target)
            self.assertEqual(fresh['selected']['new_evidence_refs'], ['E2'])
            store.save(state)
            state = store.load()
            target = state['questions'][-1]
            step(state['questions'][0])
            again = step(target)
            self.assertEqual(again['selected']['new_evidence_refs'], [])
            self.assertEqual(again['selected_thread_id'], identity)

    def test_archived_progress_is_not_new_but_later_evidence_is(self):
        for refs, expected in [(['E1'], []), (['E1', 'E2'], ['E2'])]:
            with self.subTest(refs=refs):
                state = initial_state()
                state['cycles'] = 20
                state['agenda']['started_cycle'] = 1
                first, second = question('Q1', 'one'), question('Q2', 'two')
                second['thread_evidence_refs'] = refs
                state['questions'] = [first, second]
                state['agenda']['threads'] = [dict(id='AT1', question_id='Q1', status='foreground')]
                state['agenda']['foreground_thread_id'] = 'AT1'
                state['agenda']['archived_threads'] = [dict(id='AT2', question_id='Q2', status='suspended', thread_progress_evidence_refs=['E1'])]
                decision = update_agenda(state, legacy_question=second, cycle=20)
                self.assertEqual(decision['selected']['new_evidence_refs'], expected)

    def test_ordinary_cycles_preserve_explicit_followup_and_reject_unrelated_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / 'organism.json')
            store.save(seeded_state())
            core = AgentCore(store)
            for index in range(3):
                candidate = temporal_candidate()
                candidate['id'] += str(index)
                candidate['question'] += f' Variant {index}'
                candidate['method'] += f' Variant {index}'
                core.propose_native_inquiry(candidate, enabled=True, persist=True)
            observation = dict(branch='autonomous/growth', baseline_fingerprint='fixed', tracked_files=100, python_files=20, python_source_lines=5000, test_files=12, working_tree_clean=True)
            first, second = [core.cycle(observation=observation, strict_experiment_admission=True, planning_lab=True, _now_override=f'2026-10-05T01:0{i}:00+00:00') for i in range(2)]
            self.assertEqual(first['experiment']['id'], 'X000001')
            self.assertNotEqual(first['question']['id'], first['experiment']['question_id'])
            self.assertIsNone(second['experiment'])
            self.assertEqual(first['experiment_routing']['relationship'], 'explicit_followup')
            self.assertEqual(second['experiment_routing']['target_relationship'], 'unrelated')
            self.assertEqual(second['experiment_routing']['selected_question_id'], second['question']['id'])
            event = json.loads(store.journal_path.read_text().splitlines()[-1])
            self.assertEqual(event['experiment_routing'], second['experiment_routing'])
