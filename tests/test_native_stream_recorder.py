from __future__ import annotations
import json
import sys
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from native_stream_recorder import KEY, NativeStreamRecorder
from open_object_world import initial_world, observe_world, transition
from open_object_world_explorer import choose_command, observation_signature, command_key
from open_object_world_native_bridge import temporal_candidates
from open_object_world_action_association import association_candidates
from normalized_inquiry_objectives import rank_normalized_candidates
from open_object_world_epistemic_actions import select_epistemic_command


class NativeStreamRecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = StateStore(Path(self.temp.name) / 'organism.json')
        self.store.save(initial_state())
        self.recorder = NativeStreamRecorder(self.store, 'fixture', enabled=True)
        self.world = initial_world(1)
        self.observations = [observe_world(self.world)]
        self.receipts = []
        self.attempts = Counter()

    def start(self):
        self.recorder.ingest(self.observations[0], source_id='fixture')

    def step(self, command=None):
        observation = self.observations[-1]
        command = command or choose_command(observation, self.attempts)
        self.attempts[(observation_signature(observation), command_key(command))] += 1
        self.world, receipt = transition(self.world, command, cycle=observation['cycle'] + 1)
        after = observe_world(self.world)
        self.recorder.ingest(after, receipt, source_id='fixture')
        self.observations.append(after)
        self.receipts.append(receipt)

    def history(self, count=40):
        self.start()
        for _ in range(count):
            self.step()

    def test_disabled_default_does_not_touch_store(self):
        before = self.store.path.read_bytes()
        with self.assertRaises(RuntimeError):
            NativeStreamRecorder(self.store, 'fixture')
        self.assertEqual(before, self.store.path.read_bytes())

    def test_requires_explicit_existing_copy(self):
        with self.assertRaises(ValueError):
            NativeStreamRecorder(StateStore(Path(self.temp.name)/'missing.json'), 'fixture', enabled=True)

    def test_refuses_repository_state_directory(self):
        with self.assertRaises(ValueError):
            NativeStreamRecorder(StateStore(ROOT/'state'/'organism.json'), 'fixture', enabled=True)

    def test_identical_retry_after_reload_is_byte_preserving(self):
        self.history(5)
        before = self.store.path.read_bytes()
        reloaded = NativeStreamRecorder(StateStore(self.store.path), 'fixture', enabled=True)
        self.assertFalse(reloaded.ingest(self.observations[-1], self.receipts[-1], source_id='fixture'))
        self.assertEqual(before, self.store.path.read_bytes())

    def test_conflicting_duplicate_rejected_without_mutation(self):
        self.history(2)
        bad = deepcopy(self.receipts[-1]); bad['success'] = not bad['success']
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'conflicting duplicate'):
            self.recorder.ingest(self.observations[-1], bad, source_id='fixture')
        self.assertEqual(before, self.store.path.read_bytes())

    def test_gap_and_old_sample_are_rejected(self):
        self.history(2)
        before = self.store.path.read_bytes()
        bad = deepcopy(self.observations[-1]); bad['cycle'] += 2; bad['observation_id'] = 'ow-000004'
        for observation in (bad, self.observations[0]):
            with self.assertRaises(ValueError):
                self.recorder.ingest(observation, self.receipts[-1], source_id='fixture')
            self.assertEqual(before, self.store.path.read_bytes())

    def test_source_mismatch_rejected_after_reload(self):
        self.history(1)
        with self.assertRaisesRegex(ValueError, 'source mismatch'):
            self.recorder.ingest(self.observations[-1], self.receipts[-1], source_id='another')
        other = NativeStreamRecorder(self.store, 'another', enabled=True)
        with self.assertRaisesRegex(ValueError, 'source mismatch'):
            other.publish()

    def test_hidden_observation_or_entity_fields_rejected(self):
        self.start()
        for mutation in ('top', 'entity', 'nonlocal', 'cycle', 'position'):
            bad = deepcopy(self.observations[0])
            if mutation == 'top': bad['_truth'] = True
            if mutation == 'entity': bad['visible_entities'][0]['_mass'] = 2
            if mutation == 'nonlocal': bad['visible_entities'][0]['position'] = [2, 2]
            if mutation == 'cycle': bad['cycle'] = False
            if mutation == 'position': bad['position'] = [False, 0]
            before = self.store.path.read_bytes()
            with self.assertRaises(ValueError):
                self.recorder.ingest(bad, source_id='fixture')
            self.assertEqual(before, self.store.path.read_bytes())

    def test_hidden_receipt_and_alignment_errors_rejected(self):
        self.start()
        world, receipt = transition(self.world, {'action': 'north'}, cycle=1)
        after = observe_world(world)
        for key, value in (('_seed', 1), ('cycle', 9), ('before', [2,2]), ('after', [2,2]), ('action', 'teleport')):
            bad = deepcopy(receipt); bad[key] = value
            before = self.store.path.read_bytes()
            with self.assertRaises(ValueError):
                self.recorder.ingest(after, bad, source_id='fixture')
            self.assertEqual(before, self.store.path.read_bytes())

    def test_new_source_cannot_start_mid_history(self):
        world, receipt = transition(self.world, {'action':'north'}, cycle=1)
        with self.assertRaises(ValueError):
            self.recorder.ingest(observe_world(world), receipt, source_id='fixture')

    def test_counts_come_from_values_not_receipt_success(self):
        self.start()
        world, receipt = transition(self.world, {'action':'north'}, cycle=1)
        receipt['success'] = False
        receipt['observed_effects'] = ['no_observed_change']
        self.recorder.ingest(observe_world(world), receipt, source_id='fixture')
        self.assertEqual(self.store.load()[KEY]['totals']['position']['changed'], 1)

    def test_stream_statistics_and_published_candidates_match_raw_oracle(self):
        self.history()
        self.recorder.publish()
        temporal, actions = self.recorder.candidates()
        self.assertEqual(temporal, temporal_candidates(self.observations))
        self.assertEqual(actions, association_candidates(self.observations, self.receipts, min_present=1))

    def test_read_only_decision_matches_exact_frozen_selector(self):
        self.history()
        self.recorder.publish()
        before = self.store.path.read_bytes()
        decision = NativeStreamRecorder(StateStore(self.store.path), 'fixture', enabled=True).decision()
        ranked = rank_normalized_candidates(temporal_candidates(self.observations), 'information_gain')
        candidate = ranked[0]['candidate']
        direct = select_epistemic_command(self.observations[-1], feature=candidate['feature'], relation=candidate['relation'], prefix_observations=self.observations, prefix_receipts=self.receipts)
        self.assertEqual(decision['ranked'], ranked)
        self.assertEqual(decision['selection'], direct)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_publish_retries_do_not_append_overlapping_snapshots(self):
        self.history()
        first = self.recorder.publish()
        before = self.store.path.read_bytes()
        self.assertEqual(first, self.recorder.publish())
        self.assertEqual(before, self.store.path.read_bytes())
        self.step()
        with self.assertRaises(ValueError): self.recorder.decision()
        second = self.recorder.publish()
        self.assertNotEqual(first['chain'], second['chain'])
        temporal, actions = self.recorder.candidates()
        self.assertEqual(temporal, temporal_candidates(self.observations))
        self.assertEqual(actions, association_candidates(self.observations, self.receipts, min_present=1))

    def test_partial_publication_failure_preserves_file_and_can_retry(self):
        self.history()
        before = self.store.path.read_bytes()
        original = AgentCore.record_native_evidence
        calls = 0
        def fail(core, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3: raise OSError('injected interruption')
            return original(core, *args, **kwargs)
        with patch.object(AgentCore, 'record_native_evidence', fail):
            with self.assertRaises(OSError): self.recorder.publish()
        self.assertEqual(before, self.store.path.read_bytes())
        self.recorder.publish()
        self.assertEqual(self.recorder.candidates()[0], temporal_candidates(self.observations))

    def test_failed_atomic_replace_preserves_source_cursor(self):
        self.history(3)
        before = self.store.path.read_bytes()
        world, receipt = transition(self.world, {'action':'north'}, cycle=4)
        with patch.object(Path, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.recorder.ingest(observe_world(world), receipt, source_id='fixture')
        self.assertEqual(before, self.store.path.read_bytes())
        self.recorder.ingest(observe_world(world), receipt, source_id='fixture')
        self.assertEqual(self.store.load()[KEY]['latest']['cycle'], 4)

    def test_lost_or_altered_native_evidence_fails_closed(self):
        self.history(); self.recorder.publish()
        saved = self.store.load()
        for mutate in ('lost', 'altered'):
            bad = deepcopy(saved)
            if mutate == 'lost': bad['episodes'].pop()
            else: bad['episodes'][-1]['content'] = '{}'
            self.store.save(bad)
            with self.assertRaises(ValueError): self.recorder.decision()
        self.store.save(saved)

    def test_accumulator_corruption_detected(self):
        self.history(2)
        bad = self.store.load(); bad[KEY]['totals']['position']['changed'] += 1
        self.store.save(bad)
        with self.assertRaises(ValueError): self.recorder.publish()

    def test_only_latest_raw_observation_retained_and_no_core_cycles_advanced(self):
        self.history(70); self.recorder.publish()
        state = self.store.load(); cursor = state[KEY]
        self.assertEqual(cursor['latest']['cycle'], 70)
        self.assertEqual(len(cursor['recent_refs']), 64)
        self.assertNotIn('observations', cursor)
        self.assertNotIn('receipts', cursor)
        self.assertNotIn('history', cursor)
        self.assertEqual(state['cycles'], 0)
        self.assertFalse(state['experiments'])
        self.assertFalse(state['questions'])
        self.assertFalse(self.store.journal_path.exists())

    def test_unobservable_feature_is_not_counted_as_zero_or_change(self):
        self.history(20)
        self.recorder.publish()
        temporal, _ = self.recorder.candidates()
        for candidate in temporal:
            if candidate['feature'].startswith('entity.'):
                self.assertLess(candidate['evaluable'], 20)
        self.assertEqual(temporal, temporal_candidates(self.observations))

    def test_majority_relation_can_flip_without_double_counting(self):
        self.history(3)
        for _ in range(10): self.step({'action':'inspect', 'target':'O001'})
        self.recorder.publish()
        candidates, _ = self.recorder.candidates()
        self.assertEqual(candidates, temporal_candidates(self.observations))
        self.assertEqual(next(c for c in candidates if c['feature']=='position')['relation'], 'same_next_observation')

if __name__ == '__main__':
    unittest.main()
