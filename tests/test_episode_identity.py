from __future__ import annotations
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from agenttest.core import AgentCore
from agenttest.evidence import known_evidence_ids
from agenttest.episode_identity import allocate_episode_id, ensure_episode_sequence
from agenttest.state import StateStore, initial_state, migrate_state
from tests.test_native_inquiry_resolution import temporal_evidence, temporal_candidate

class EpisodeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = StateStore(Path(self.tmp.name)/'organism.json')
        self.store.save(initial_state()); self.core=AgentCore(self.store)

    def record(self):
        return self.core.record_native_evidence(temporal_evidence(), enabled=True, persist=True)

    def test_initial_index_and_first_identity_preserve_legacy_behavior(self):
        self.assertEqual(initial_state()['next_episode_index'],1)
        self.assertEqual(self.record()['evidence_ref'],'E000001')
        self.assertEqual(self.store.load()['next_episode_index'],2)

    def test_dense_legacy_migration_changes_only_metadata(self):
        self.record(); self.record()
        legacy=self.store.load(); legacy.pop('next_episode_index')
        original=deepcopy(legacy); expected_refs=known_evidence_ids(legacy)
        migrated=migrate_state(legacy)
        self.assertEqual(migrated['next_episode_index'],3)
        comparable=deepcopy(migrated); comparable.pop('next_episode_index')
        self.assertEqual(comparable,original)
        self.assertEqual(known_evidence_ids(migrated),expected_refs)

    def test_migration_is_idempotent(self):
        self.record(); state=self.store.load()
        self.assertEqual(migrate_state(deepcopy(state)),state)

    def test_sparse_legacy_ids_migrate_past_highest_not_list_length(self):
        state=initial_state(); state.pop('next_episode_index')
        state['episodes']=[{'id':'E000001'}, {'id':'E000099'}]
        original=deepcopy(state['episodes'])
        self.assertEqual(allocate_episode_id(state),'E000100')
        self.assertEqual(state['episodes'],original)

    def test_middle_removal_does_not_reuse_retained_id(self):
        for _ in range(3): self.record()
        state=self.store.load(); state['episodes'].pop(1); self.store.save(state)
        self.assertEqual(self.record()['evidence_ref'],'E000004')
        ids=[e['id'] for e in self.store.load()['episodes']]
        self.assertEqual(ids,['E000001','E000003','E000004'])

    def test_highest_removed_id_stays_reserved_after_reload(self):
        for _ in range(3): self.record()
        state=self.store.load(); state['episodes'].pop(); self.store.save(state)
        self.core=AgentCore(StateStore(self.store.path))
        self.assertEqual(self.record()['evidence_ref'],'E000004')

    def test_empty_retained_ledger_does_not_reset_saved_watermark(self):
        self.record(); self.record()
        state=self.store.load(); state['episodes']=[]; self.store.save(state)
        self.assertEqual(self.record()['evidence_ref'],'E000003')

    def test_stale_low_watermark_advances_without_rewriting_ids(self):
        state=initial_state(); state['episodes']=[{'id':'E000010'}]
        self.assertEqual(ensure_episode_sequence(state),11)
        self.assertEqual(state['episodes'][0]['id'],'E000010')

    def test_high_watermark_never_decreases(self):
        state=initial_state(); state['next_episode_index']=500
        for _ in range(3): self.assertEqual(ensure_episode_sequence(state),500)
        self.assertEqual(allocate_episode_id(state),'E000500')

    def test_six_digit_width_is_minimum_not_a_wrapping_limit(self):
        state=initial_state(); state['next_episode_index']=1000000
        self.assertEqual(allocate_episode_id(state),'E1000000')
        self.assertEqual(state['next_episode_index'],1000001)

    def test_opaque_historical_ids_are_preserved_not_rewritten(self):
        state=initial_state(); state['episodes']=[{'id':'external.episode'}]
        self.assertEqual(allocate_episode_id(state),'E000002')
        self.assertEqual(state['episodes'][0]['id'],'external.episode')

    def test_invalid_watermark_fails_before_disk_mutation(self):
        before=self.store.path.read_bytes()
        for value in (0,-1,True,False,None,1.2,'3',{}):
            with self.subTest(value=value):
                state=self.store.load(); state['next_episode_index']=value
                with self.assertRaises(ValueError): self.store.save(state)
                self.assertEqual(self.store.path.read_bytes(),before)

    def test_duplicate_ids_are_rejected_not_renamed(self):
        state=self.store.load(); state['episodes']=[{'id':'E000001'},{'id':'E000001'}]
        before=self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'duplicate episode'): self.store.save(state)
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertEqual(state['episodes'][0],state['episodes'][1])

    def test_corrupt_legacy_file_fails_on_load_without_repairing_file(self):
        state=initial_state(); state.pop('next_episode_index')
        state['episodes']=[{'id':'E000001'},{'id':'E000001'}]
        self.store.path.write_text(json.dumps(state)); before=self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'duplicate episode'): self.store.load()
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_load_only_migration_does_not_write_source(self):
        state=initial_state(); state.pop('next_episode_index')
        state['episodes']=[{'id':'E000004'}]
        self.store.path.write_text(json.dumps(state)); before=self.store.path.read_bytes()
        self.assertEqual(self.store.load()['next_episode_index'],5)
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_nonpersisting_native_record_does_not_advance_stored_counter(self):
        before=self.store.path.read_bytes()
        result=self.core.record_native_evidence(temporal_evidence(),enabled=True)
        self.assertEqual(result['evidence_ref'],'E000001')
        self.assertEqual(result['state']['next_episode_index'],2)
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertEqual(self.record()['evidence_ref'],'E000001')

    def test_failed_atomic_save_leaves_counter_and_history_unchanged(self):
        self.record(); before=self.store.path.read_bytes()
        with patch.object(Path,'replace',side_effect=OSError('injected save failure')):
            with self.assertRaises(OSError): self.record()
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertEqual(self.record()['evidence_ref'],'E000002')

    def test_fresh_native_resolution_survives_metadata_migration(self):
        grounding=self.record()
        inquiry=self.core.propose_native_inquiry(temporal_candidate(grounding['evidence_ref']),enabled=True,persist=True)
        original=self.store.load(); floor=inquiry['experiment']['native_inquiry']['resolution_evidence_floor_episode_count']
        legacy=deepcopy(original); legacy.pop('next_episode_index'); self.store.path.write_text(json.dumps(legacy))
        fresh=temporal_evidence(refs=['after-a','after-b'])
        result=AgentCore(StateStore(self.store.path)).record_native_evidence(fresh,enabled=True,persist=True)
        self.assertEqual(result['evidence_ref'],'E000002')
        resolved=AgentCore(StateStore(self.store.path)).resolve_native_inquiry(inquiry['experiment']['id'],result['evidence_ref'],enabled=True,persist=True)
        self.assertEqual(resolved['experiment']['status'],'completed')
        self.assertEqual(self.store.load()['experiments'][0]['native_inquiry']['resolution_evidence_floor_episode_count'],floor)

    def test_watermark_is_not_added_to_known_evidence_authority(self):
        before=known_evidence_ids(self.store.load())
        state=self.store.load(); state['next_episode_index']=999; self.store.save(state)
        self.assertEqual(known_evidence_ids(self.store.load()),before)

    def test_no_pruning_occurs_in_normal_record_and_cycle(self):
        self.record(); original=deepcopy(self.store.load()['episodes'])
        self.core.cycle(stimulus='continue',_now_override='2026-10-05T00:00:00+00:00')
        after=self.store.load()
        self.assertEqual(after['episodes'][:len(original)],original)
        ids=[e['id'] for e in after['episodes']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(after['next_episode_index'],len(ids)+1)

if __name__=='__main__': unittest.main()
