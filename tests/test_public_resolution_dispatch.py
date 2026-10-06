"""Focused zero-cycle gate using retained V4 objects, never a new trajectory."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agenttest.core as core
from agenttest.state import StateStore, initial_state
from agenttest.public_observation import KEY, plan_public_resolutions, registry_eligible

CLOCK = '2026-10-06T03:00:00+00:00'

def typed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

class PublicDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).resolve().parent/'fixtures/public_resolution_dispatch'
        provenance = json.loads((fixture/'PROVENANCE.json').read_text())
        raw = (fixture/'retained-state.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=provenance['retained_state_sha256']:
            raise AssertionError('retained projected fixture changed')
        state = json.loads(raw)
        cls.fixture = state
        cls.bound = []
        for source_id, source in state[KEY]['sources'].items():
            for pair_id, bindings in source['pair_evidence'].items():
                for relation, ref in bindings.items():
                    ep = next(e for e in state['episodes'] if e['id']==ref)
                    if ep['cycle']==state['cycles']:
                        cls.bound.append({'source_id':source_id,'pair_id':pair_id,'relation':relation,'evidence_ref':ref})
        raw_wrapper = (fixture/'original_explicit_wrapper.py').read_bytes()
        if hashlib.sha256(raw_wrapper).hexdigest()!=provenance['original_wrapper_sha256']:
            raise AssertionError('original wrapper fixture changed')
        tree = ast.parse(raw_wrapper.decode())
        klass = next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method = next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='resolve_native_inquiry')
        namespace = dict(vars(core))
        exec(compile(ast.Module(body=[method],type_ignores=[]), '<frozen-original-explicit-wrapper>', 'exec'), namespace)
        cls.original_wrapper = staticmethod(namespace['resolve_native_inquiry'])

    def setUp(self):
        self.state = deepcopy(self.fixture)
        self.rows = deepcopy(self.bound)

    def assertExact(self,a,b):
        self.assertEqual(typed(a),typed(b))

    def expected(self):
        """Independent full expected transition, derived from actual raw pair."""
        expected = deepcopy(self.state)
        e = expected['experiments'][0]
        c = e['public_observation_contract']
        row = next(r for r in self.rows if r['evidence_ref']=='E014476')
        source = expected[KEY]['sources'][row['source_id']]
        before, after = [json.loads(raw)['payload'] for raw in source['raw_records'][1:3]]
        entity_id = c['feature_tuple'][1]
        left = next(v['observable_state'] for v in before['visible_entities'] if v['id']==entity_id)
        right = next(v['observable_state'] for v in after['visible_entities'] if v['id']==entity_id)
        self.assertEqual(left,right)
        evidence = json.loads(next(ep['content'] for ep in expected['episodes'] if ep['id']=='E014476'))
        self.assertEqual(evidence['measurement'],{'evaluable':1,'confirmations':0,'refutations':1})
        identity = {'experiment_id':e['id'],'source_id':c['source_id'],'family_id':c['family_id'],
                    'version_id':c['version_id'],'floor_hash':c['outcome_floor_record_hash'],
                    'pair_id':row['pair_id'],'relation':row['relation']}
        key = hashlib.sha256(typed(identity).encode()).hexdigest()
        reflection_id = f"R{len(expected['reflections'])+1:06d}"
        receipt = {'version':'public-resolution-dispatch-v1','key':key,**identity,
                   'evidence_ref':'E014476','outcome':'falsified','reflection_id':reflection_id}
        e.update(status='completed',readiness='resolved',outcome='falsified',evidence_strength=1.0,
                 evidence_refs=['E014476'],completion_source='native_evidence_contract',completed_at=CLOCK,
                 native_resolution={'version':'native-inquiry-resolution-v1','evidence_ref':'E014476',
                                    'relation':deepcopy(evidence['relation']),'measurement_kind':'binary_transition_outcomes','outcome':'falsified'},
                 public_resolution_receipt=receipt)
        e.setdefault('status_history',[]).append({'cycle':expected['cycles'],'from':'proposed','to':'completed',
            'reason':'native_evidence_contract_resolved','evidence_refs':['E014476'],'outcome':'falsified','public_resolution_key':key})
        expected['reflections'].append({'id':reflection_id,'source':'native_inquiry','experiment_id':e['id'],
            'evidence_ref':'E014476','cycle':expected['cycles'],'outcome':'falsified','evidence_strength':1.0,
            'lesson':'One matching evaluable native transition falsified the bounded temporal inquiry. Treat this as an experiment outcome, not as a general causal fact.',
            'public_resolution_key':key})
        return expected

    def test_exhausted_owned_allocation_closes_exactly_without_selection(self):
        self.assertFalse(registry_eligible(self.state,self.state['questions'][0]))
        before = deepcopy(self.state)
        result, receipts = core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
        self.assertExact(result,self.expected())
        self.assertExact(self.state,before)
        self.assertEqual(receipts[0]['status'],'resolved')
        self.assertFalse(registry_eligible(result,result['questions'][0]))

    def test_no_bindings_does_not_process_historical_backlog(self):
        result, receipts = core._dispatch_public_resolutions(self.state,[],CLOCK)
        self.assertExact(result,self.state)
        self.assertEqual(receipts,[])

    def test_missing_exact_pair_does_not_search_another_feature(self):
        rows = [r for r in self.rows if r['evidence_ref']!='E014476']
        result, receipts = core._dispatch_public_resolutions(self.state,rows,CLOCK)
        self.assertExact(result,self.state)
        self.assertEqual(receipts,[{'experiment_id':'X004832','status':'not_yet_evaluable'}])

    def test_negative_provenance_and_ambiguity_table(self):
        cases = {
            'duplicate_binding':lambda s,r:r.append(deepcopy(r[0])),
            'duplicate_experiment':lambda s,r:s['experiments'].append(deepcopy(s['experiments'][0])),
            'duplicate_owner':lambda s,r:s['questions'].append(deepcopy(s['questions'][0])),
            'duplicate_episode':lambda s,r:s['episodes'].append(deepcopy(next(e for e in s['episodes'] if e['id']=='E014476'))),
            'wrong_owner':lambda s,r:s['experiments'][0].update(question_id='missing-owner'),
            'forged_hash':lambda s,r:s['experiments'][0]['public_observation_contract'].update(outcome_floor_record_hash='0'*64),
            'forged_version':lambda s,r:s['experiments'][0]['public_observation_contract'].update(version_id='POV:'+'0'*48),
            'stale_floor':lambda s,r:s['experiments'][0]['native_inquiry'].update(resolution_evidence_floor_episode_sequence=14476),
            'forged_relation':lambda s,r:s['experiments'][0]['native_inquiry']['relation'].update(feature='pub.forged'),
            'historical_episode':lambda s,r:s.update(cycles=4855),
            'forged_binding':lambda s,r:r[0].update(evidence_ref='E014465'),
        }
        for name, corrupt in cases.items():
            with self.subTest(name=name):
                state, rows = deepcopy(self.state),deepcopy(self.rows)
                corrupt(state,rows)
                before = deepcopy(state)
                with self.assertRaises((ValueError,KeyError)):
                    core._dispatch_public_resolutions(state,rows,CLOCK)
                self.assertExact(state,before)

    def test_forged_outcome_payload_rejects(self):
        ep = next(e for e in self.state['episodes'] if e['id']=='E014476')
        value = json.loads(ep['content']);value['measurement']['confirmations']=1;value['measurement']['refutations']=0
        ep['content']=json.dumps(value)
        before = deepcopy(self.state)
        with self.assertRaises(ValueError):core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
        self.assertExact(self.state,before)

    def test_current_version_cannot_replace_allocation_contract(self):
        e=self.state['experiments'][0];entry=self.state[KEY]['families'][e['public_observation_family']]
        e['public_observation_contract']=deepcopy(self.state[KEY]['versions'][entry['version_id']])
        before=deepcopy(self.state)
        with self.assertRaises(ValueError):core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
        self.assertExact(self.state,before)

    def test_replay_is_exact_noop_and_conflicting_receipts_reject(self):
        result,_=core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
        replay,receipts=core._dispatch_public_resolutions(result,self.rows,CLOCK)
        self.assertExact(replay,result);self.assertEqual(receipts[0]['status'],'already_resolved')
        for field in ('key','outcome','reflection_id'):
            state=deepcopy(result);state['experiments'][0]['public_resolution_receipt'][field]='conflict'
            before=deepcopy(state)
            with self.assertRaises(ValueError):core._dispatch_public_resolutions(state,self.rows,CLOCK)
            self.assertExact(state,before)

    def test_application_exception_after_scratch_mutation_is_atomic(self):
        def corrupt_then_fail(state,*args):
            state['experiments'][0]['status']='completed'
            raise RuntimeError('injected application failure')
        before=deepcopy(self.state)
        with patch.object(core,'_resolve_native_inquiry_state',side_effect=corrupt_then_fail):
            with self.assertRaises(RuntimeError):core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
        self.assertExact(self.state,before)

    def test_mixed_ambiguous_batch_never_applies_valid_member(self):
        other=deepcopy(self.state['experiments'][0]);other['id']='other';self.state['experiments'].append(other)
        before=deepcopy(self.state)
        with patch.object(core,'_resolve_native_inquiry_state',side_effect=AssertionError('must not apply')) as apply:
            with self.assertRaises(ValueError):core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
        self.assertEqual(apply.call_count,0);self.assertExact(self.state,before)

    def test_guard_default_off_and_explicit_copy_required(self):
        core._guard_public_dispatch('state/organism.json',False,None)
        with self.assertRaises(ValueError):core._guard_public_dispatch('state/organism.json',True,'inlet')
        with self.assertRaises(ValueError):core._guard_public_dispatch('copied.json',True,None)
        with self.assertRaises(ValueError):core._guard_public_dispatch('copied.json',1,'inlet')
        core._guard_public_dispatch('copied.json',True,'inlet')

    def test_explicit_wrapper_matches_frozen_original_without_cycle(self):
        for persist in (False,True):
            with self.subTest(persist=persist),tempfile.TemporaryDirectory() as directory:
                stores=[StateStore(Path(directory)/name/'organism.json') for name in ('old','new')]
                with patch('agenttest.state.utc_now',return_value=CLOCK):
                    for store in stores:store.save(deepcopy(self.state))
                    old=self.original_wrapper(core.AgentCore(stores[0]),'X004832','E014476',enabled=True,persist=persist,_now_override=CLOCK)
                    new=core.AgentCore(stores[1]).resolve_native_inquiry('X004832','E014476',enabled=True,persist=persist,_now_override=CLOCK)
                self.assertExact(old,new);self.assertEqual(stores[0].path.read_bytes(),stores[1].path.read_bytes())
                with self.assertRaises(RuntimeError):core.AgentCore(stores[1]).resolve_native_inquiry('X004832','E014476')

    def test_save_failure_propagates_without_replacing_previous_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store=StateStore(Path(directory)/'organism.json')
            with patch('agenttest.state.utc_now',return_value=CLOCK):store.save(deepcopy(self.state))
            before=store.path.read_bytes()
            with patch('pathlib.Path.replace',side_effect=OSError('injected save failure')):
                with self.assertRaises(OSError):core.AgentCore(store).resolve_native_inquiry('X004832','E014476',enabled=True,persist=True,_now_override=CLOCK)
            self.assertEqual(store.path.read_bytes(),before)

    def test_saved_closure_survives_journal_failure_without_duplicate_resolution(self):
        """Persistence seam only; does not claim a complete cycle or crash atomicity."""
        with tempfile.TemporaryDirectory() as directory:
            store=StateStore(Path(directory)/'organism.json')
            result,_=core._dispatch_public_resolutions(self.state,self.rows,CLOCK)
            with patch('agenttest.state.utc_now',return_value=CLOCK):store.save(result)
            saved=store.path.read_bytes()
            with patch.object(store,'append_journal',side_effect=OSError('injected append failure')):
                with self.assertRaises(OSError):store.append_journal({'event':'copied-persistence-seam'})
            self.assertEqual(store.path.read_bytes(),saved);self.assertFalse(store.journal_path.exists())
            replay,receipts=core._dispatch_public_resolutions(store.load(),self.rows,CLOCK)
            self.assertExact(replay,store.load());self.assertEqual(receipts[0]['status'],'already_resolved')
