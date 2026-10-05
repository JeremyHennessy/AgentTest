"""Frozen public fixtures; no world transitions, staging, cognition or live writes."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenttest import public_observation as public
from agenttest.agenda import _candidate_metrics, _eligible_questions
from agenttest.core import AgentCore
from agenttest.perception import repository_snapshot
from agenttest.state import StateStore, initial_state

FIXTURES=Path(__file__).parent/'fixtures'/'public_observation'
CLOCK='2026-10-05T21:20:00+00:00'


def bundle(name):
    return public.load_bundle(FIXTURES/name)


def changed(original, mutate):
    result=deepcopy(original); record=public.decode(result['raw_record'])
    mutate(record)
    record['payload_sha256']=public.digest(record['payload'])
    if record['sequence']==1:
        result['descriptor']['genesis_payload_sha256']=record['payload_sha256']
    record['source_descriptor_sha256']=public.digest(result['descriptor'])
    record['record_sha256']=public.digest({k:v for k,v in record.items() if k!='record_sha256'})
    result['raw_record']=public.canonical(record).decode()
    result['acquisition_manifest']['descriptor_sha256']=public.digest(result['descriptor'])
    import hashlib
    result['acquisition_manifest']['ordered_raw_record_sha256'][record['sequence']-1]=hashlib.sha256(result['raw_record'].encode()).hexdigest()
    return result


def variant_stream(mutate, descriptor_mutate=lambda descriptor: None):
    """One named fixture mutation; reconstruct integrity without choosing a question."""
    import hashlib
    templates=[bundle(f'synthetic-{i}.json') for i in range(1,4)]
    records=[public.decode(t['raw_record']) for t in templates]
    mutate(records)
    descriptor=deepcopy(templates[0]['descriptor'])
    descriptor_mutate(descriptor)
    descriptor['genesis_payload_sha256']=public.digest(records[0]['payload'])
    prior=None; raw=[]
    for r in records:
        r['source_descriptor_sha256']=public.digest(descriptor); r['previous_record_sha256']=prior
        r['payload_sha256']=public.digest(r['payload'])
        r['record_sha256']=public.digest({k:v for k,v in r.items() if k!='record_sha256'})
        prior=r['record_sha256']; raw.append(public.canonical(r).decode())
    acquisition={'version':'public-acquisition-v1','descriptor_sha256':public.digest(descriptor),'ordered_raw_record_sha256':[hashlib.sha256(r.encode()).hexdigest() for r in raw]}
    return [{'descriptor':descriptor,'acquisition_manifest':acquisition,'raw_record':r} for r in raw]


class PublicObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.store=StateStore(self.root/'copy'/'ora.json')
        state=initial_state(); state['cycles']=10; state['generation']=10; state['agenda']['started_cycle']=1
        self.store.save(state)
        self.observation=repository_snapshot(Path(__file__).resolve().parents[1])

    def cycle(self, value):
        path=self.root/'observation.json'; path.write_bytes(public.canonical(value))
        # These APIs are forbidden even if an implementation accidentally adds a call.
        with patch.object(AgentCore,'propose_native_inquiry',side_effect=AssertionError('staging bypass')), patch.object(AgentCore,'resolve_native_inquiry',side_effect=AssertionError('resolution bypass')), patch('agenttest.core.run_cognition',side_effect=AssertionError('model bypass')):
            return AgentCore(self.store).cycle('autonomous heartbeat',self.observation,strict_experiment_admission=True,planning_lab=True,_now_override=CLOCK,copy_public_observations=path)

    def accepted_two(self):
        self.cycle(bundle('synthetic-1.json'))
        result=self.cycle(bundle('synthetic-2.json'))
        return result,self.store.load()

    def rejected_without_save(self,value):
        before=self.store.path.read_bytes(); journal=self.store.journal_path.read_bytes() if self.store.journal_path.exists() else None
        with self.assertRaises((ValueError,TypeError,KeyError)):
            self.cycle(value)
        self.assertEqual(before,self.store.path.read_bytes())
        self.assertEqual(journal,self.store.journal_path.read_bytes() if self.store.journal_path.exists() else None)

    def test_passive_genuine_seed1_stops_with_zero_pairs(self):
        first=bundle('passive-1.json'); self.assertEqual(public.decode(first['raw_record'])['payload']['position'],[-2,0])
        result=self.cycle(first); trace=result['public_observation_trace']
        self.assertEqual(trace['pairs'],[]); self.assertEqual(trace['contracts'],[])
        self.assertFalse(trace['native_selected']); self.assertEqual(trace['selection_status'],'zero_pairs_stop')
        self.assertIsNotNone(result['planning_lab_result'])

    def test_exhaustive_complements_eligible_defer_and_exhaustion(self):
        result,state=self.accepted_two(); trace=result['public_observation_trace']
        self.assertEqual(len(trace['pairs']),8); self.assertEqual(len(trace['contracts']),8)
        self.assertEqual(len(trace['eligible_families']),8)
        self.assertEqual(trace['selection_status'],'ordinary_defer'); self.assertIsNone(trace['allocation_id'])
        self.assertEqual(result['agenda_decision']['selected']['question_id'],result['agenda_decision']['legacy_counterfactual']['question_id'])
        questions=[q for q in state['questions'] if q.get('source')==public.SOURCE]
        self.assertEqual(len(questions),8)
        for q in questions:
            metrics=_candidate_metrics(state,q,legacy_question_id=result['question']['id'],prior_thread=None)
            self.assertEqual(metrics['priority_score'],0); self.assertEqual(metrics['new_evidence_refs'],[])
            self.assertFalse(metrics['active_experiment_path']); self.assertTrue(public.registry_eligible(state,q))
        self.assertFalse(any(x.get('public_observation_family') for x in state['experiments']))
        last=self.cycle(bundle('synthetic-3.json')); after=self.store.load()
        self.assertEqual(last['public_observation_trace']['selection_status'],'exhausted')
        self.assertEqual(len(after[public.KEY]['versions']),16)
        self.assertEqual({q['id'] for q in questions},{q['id'] for q in after['questions'] if q.get('source')==public.SOURCE})
        self.assertFalse(any(public.registry_eligible(after,q) for q in after['questions'] if q.get('source')==public.SOURCE))

    def test_restart_replay_any_prior_record_is_idempotent(self):
        _,state=self.accepted_two(); before=deepcopy(state[public.KEY])
        for name in ('synthetic-1.json','synthetic-2.json'):
            result=public.ingest(state,bundle(name)); self.assertEqual(result['status'],'idempotent_replay')
        self.assertEqual(before,state[public.KEY])
        self.store.save(state); reloaded=self.store.load()
        self.assertEqual(before,reloaded[public.KEY])

    def test_conflict_noncontiguous_broken_chain_no_mutation(self):
        self.cycle(bundle('synthetic-1.json'))
        self.rejected_without_save(changed(bundle('synthetic-1.json'),lambda r:r['payload']['inventory_ids'].reverse()))
        self.rejected_without_save(bundle('synthetic-3.json'))
        self.rejected_without_save(changed(bundle('synthetic-2.json'),lambda r:r.update(previous_record_sha256='0'*64)))

    def test_unknown_preferred_hidden_fields_and_payload_negatives(self):
        mutations=[lambda r:r.update(preferred_question='chosen'),lambda r:r.update(objective_score=1),
                   lambda r:r['payload'].update(_kind='hidden'),lambda r:r['payload'].update(world_version='unsupported'),
                   lambda r:r['payload'].update(position=[3,0]),lambda r:r['payload'].update(position=[-3,0]),
                   lambda r:r['payload'].update(position=[True,0]),lambda r:r['payload'].update(inventory_ids=['A','A']),
                   lambda r:r['payload']['visible_entities'].append(deepcopy(r['payload']['visible_entities'][0])),
                   lambda r:r['payload']['visible_entities'][0].update(position=[2,2]),
                   lambda r:r.update(observed_at='2026-10-04T00:00:00Z'),lambda r:r.update(observed_at='2026-10-05T00:00:00+00:00')]
        for mutate in mutations:
            with self.subTest(mutation=mutate): self.rejected_without_save(changed(bundle('synthetic-1.json'),mutate))

    def test_duplicate_keys_nonfinite_size_absent_file_no_save(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(ValueError): public.decode(raw)
            value=bundle('synthetic-1.json'); value['raw_record']=raw
            self.rejected_without_save(value)
        value=bundle('synthetic-1.json'); value['raw_record']='x'*(public.MAX_BYTES+1)
        self.rejected_without_save(value)
        before=self.store.path.read_bytes()
        with self.assertRaises(FileNotFoundError): AgentCore(self.store).cycle(copy_public_observations=self.root/'absent')
        self.assertEqual(before,self.store.path.read_bytes())

    def test_unsorted_inventory_and_boundaries_preserved(self):
        value=bundle('synthetic-1.json'); public.validate_bundle(value)
        self.assertEqual(public.decode(value['raw_record'])['payload']['inventory_ids'],['O002','O001'])
        for position in ([-2,0],[2,0]):
            value=changed(bundle('synthetic-1.json'),lambda r:r['payload'].update(position=position,visible_entities=[]))
            public.validate_bundle(value)

    def test_missing_middle_and_repeated_cycle_do_not_form_pair(self):
        source=deepcopy(bundle('synthetic-1.json')['descriptor'])
        raw_records=[bundle(f'synthetic-{i}.json')['raw_record'] for i in range(1,4)]
        middle=public.decode(raw_records[1]); del middle['payload']['visible_entities'][0]['observable_state']
        raw_records[1]=public.canonical(middle).decode()
        pairs=public._pairs({'descriptor':source,'raw_records':raw_records})
        self.assertFalse(any(p['feature']==['entity','E001','state'] for p in pairs.values()))
        first=public.decode(raw_records[0]); middle['payload']['cycle']=first['payload']['cycle']
        pairs=public._pairs({'descriptor':source,'raw_records':[raw_records[0],public.canonical(middle).decode()]})
        self.assertEqual(pairs,{})

    def test_accepted_missing_middle_never_skips_to_visible_later(self):
        stream=variant_stream(lambda rows:rows[1]['payload']['visible_entities'][0].pop('observable_state'))
        results=[self.cycle(value) for value in stream]
        for result in results[1:]:
            self.assertEqual(len(result['public_observation_trace']['pairs']),6)
            self.assertFalse(any(c['feature_tuple']==['entity','E001','state'] for c in result['public_observation_trace']['contracts']))

    def test_repeated_cycle_rejects_with_zero_pairs_at_repeat(self):
        stream=variant_stream(lambda rows:rows[1]['payload'].update(cycle=rows[0]['payload']['cycle']))
        self.cycle(stream[0]); self.rejected_without_save(stream[1])
        source=next(iter(self.store.load()[public.KEY]['sources'].values()))
        self.assertEqual(source['pair_evidence'],{})

    def test_same_readable_feature_in_two_worlds_cannot_cross_ground(self):
        _,state=self.accepted_two(); first_source=next(iter(state[public.KEY]['sources']))
        first=public.compile_candidates(state,first_source)
        originals=[bundle(f'synthetic-{i}.json') for i in range(1,4)]
        import hashlib
        descriptor=deepcopy(originals[0]['descriptor']); descriptor['world_instance_id']='different-fresh-instance'
        raw=[]; prior=None
        for original in originals:
            r=public.decode(original['raw_record']); r['world_instance_id']=descriptor['world_instance_id']
            r['source_descriptor_sha256']=public.digest(descriptor); r['previous_record_sha256']=prior
            r['record_sha256']=public.digest({k:v for k,v in r.items() if k!='record_sha256'})
            prior=r['record_sha256']; raw.append(public.canonical(r).decode())
        manifest={'version':'public-acquisition-v1','descriptor_sha256':public.digest(descriptor),'ordered_raw_record_sha256':[hashlib.sha256(r.encode()).hexdigest() for r in raw]}
        for r in raw[:2]: self.cycle({'descriptor':descriptor,'acquisition_manifest':manifest,'raw_record':r})
        state=self.store.load(); second=public.compile_candidates(state,public.digest(descriptor))
        self.assertEqual({tuple(c['feature_tuple']) for c in first},{tuple(c['feature_tuple']) for c in second})
        self.assertTrue({c['candidate']['relation']['feature'] for c in first}.isdisjoint({c['candidate']['relation']['feature'] for c in second}))
        c=second[0]; wrong=first[0]['candidate']['evidence_refs'][0]
        source=state[public.KEY]['sources'][c['source_id']]
        relation=c['candidate']['relation']['kind']; source['pair_evidence'][c['pair_ids'][0]][relation]=wrong
        with self.assertRaises(ValueError): public.compile_candidates(state,c['source_id'])

    def test_compiler_pure_counts_refs_namespace_and_future_only(self):
        _,state=self.accepted_two(); source_id=next(iter(state[public.KEY]['sources']))
        before=deepcopy(state); contracts=public.compile_candidates(state,source_id); self.assertEqual(before,state)
        c=contracts[0]
        with self.assertRaises(ValueError): public.prospective_outcome(state,c,bundle('synthetic-1.json')['raw_record'],bundle('synthetic-2.json')['raw_record'])
        self.assertIsInstance(public.prospective_outcome(state,c,bundle('synthetic-2.json')['raw_record'],bundle('synthetic-3.json')['raw_record']),bool)
        episode=next(e for e in state['episodes'] if e['id']==c['candidate']['evidence_refs'][0])
        payload=json.loads(episode['content']); payload['relation']['feature']='pub.other-source'; episode['content']=json.dumps(payload)
        with self.assertRaises(ValueError): public.compile_candidates(state,source_id)

    def test_label_flag_thread_receipt_never_authorize_allocation(self):
        result,state=self.accepted_two(); q=next(q for q in state['questions'] if q.get('source')==public.SOURCE)
        self.assertIsNone(public.allocate_selected(state,q,None,CLOCK))
        fake=deepcopy(result['agenda_decision']); fake['selected']['question_id']=q['id']
        self.assertIsNone(public.allocate_selected(state,q,fake,CLOCK))
        original=deepcopy(state['experiments']); q['eligibility_flag']=True; q['thread_id']='ATfake'
        self.assertIsNone(AgentCore(self.store)._select_or_propose_experiment(state,q,{'kind':'resolve_pending_evidence','target':state['experiments'][0]['id']},None,require_grounded=True))
        self.assertEqual(original,state['experiments'])
        q['public_observation_family']='forged'
        self.assertFalse(public.registry_eligible(state,q))
        self.assertNotIn(q,_eligible_questions(state,legacy_question_id=result['question']['id'],existing_question_ids={q['id']}))

    def test_off_mode_never_loads_public_file_or_creates_key(self):
        with patch('agenttest.core.load_public_bundle',side_effect=AssertionError('off read')):
            result=AgentCore(self.store).cycle('autonomous heartbeat',self.observation,strict_experiment_admission=True,planning_lab=True,_now_override=CLOCK)
        self.assertNotIn(public.KEY,self.store.load()); self.assertNotIn('public_observation_trace',result)

    def test_outcome_rejects_repeated_identity_and_backward_time_without_mutation(self):
        for name, mutate in [
            ('duplicate_previous', lambda rows: rows[2]['payload'].update(observation_id=rows[1]['payload']['observation_id'])),
            ('duplicate_earlier', lambda rows: rows[2]['payload'].update(observation_id=rows[0]['payload']['observation_id'])),
            ('backward_time', lambda rows: rows[2].update(observed_at='2026-10-05T21:16:50Z')),
            ('repeated_cycle', lambda rows: rows[2]['payload'].update(cycle=rows[1]['payload']['cycle'])),
        ]:
            with self.subTest(name=name):
                self.setUp()
                stream=variant_stream(mutate,lambda descriptor: descriptor.update(acquisition_start='2026-10-05T21:16:50Z'))
                self.cycle(stream[0]); self.cycle(stream[1]); state=self.store.load()
                source_id=public.digest(stream[0]['descriptor'])
                contract=public.compile_candidates(state,source_id)[0]; before=deepcopy(state)
                with self.assertRaises(ValueError):
                    public.prospective_outcome(state,contract,stream[1]['raw_record'],stream[2]['raw_record'])
                self.assertEqual(before,state)
                self.rejected_without_save(stream[2])

    def test_compiler_rejects_resealed_retained_duplicate_identity_with_new_bindings(self):
        _,state=self.accepted_two(); source_id=next(iter(state[public.KEY]['sources']))
        source=state[public.KEY]['sources'][source_id]
        old_pairs=public._pairs(source); old_bindings=deepcopy(source['pair_evidence'])
        stream=variant_stream(lambda rows: rows[1]['payload'].update(observation_id=rows[0]['payload']['observation_id']))
        source['acquisition_manifest']=stream[0]['acquisition_manifest']
        source['raw_records']=[row['raw_record'] for row in stream[:2]]
        new_pairs=public._pairs(source)
        source['pair_evidence']={new_id:old_bindings[next(old_id for old_id,old in old_pairs.items() if old['feature']==pair['feature'])] for new_id,pair in new_pairs.items()}
        before=deepcopy(state)
        with self.assertRaises(ValueError): public.compile_candidates(state,source_id)
        for q in state['questions']:
            if q.get('source')==public.SOURCE: self.assertFalse(public.registry_eligible(state,q))
        self.assertEqual(before,state)

    def test_retained_policy_version_and_malformed_registry_fail_closed_without_mutation(self):
        _,original=self.accepted_two(); q=next(q for q in original['questions'] if q.get('source')==public.SOURCE)
        family=q['public_observation_family']; source_id=original[public.KEY]['families'][family]['source_id']
        def alias_version(registry):
            entry=registry['families'][family]; registry['versions']['noncanonical']=registry['versions'][entry['version_id']]
            entry['version_id']='noncanonical'
        mutations=[lambda r:r.update(version='unsupported-policy'),alias_version,
                   lambda r:r['sources'][source_id].update(raw_records=[]),
                   lambda r:r.update(families=[]),lambda r:r['families'].update({family:[]}),
                   lambda r:r.update(sources=[]),lambda r:r.update(versions=[]),
                   lambda r:r['sources'][source_id].update(pair_evidence=[])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                state=deepcopy(original); mutate(state[public.KEY]); before=deepcopy(state)
                self.assertFalse(public.registry_eligible(state,q)); self.assertEqual(before,state)
                with self.assertRaises(ValueError): public.ingest(state,bundle('synthetic-1.json'))
                self.assertEqual(before,state)

    def test_counterfactual_replay_preserves_frozen_public_input_and_cycle_flags(self):
        import agenttest.core as core_module
        self.cycle(bundle('synthetic-1.json'))
        original_cycle=AgentCore.cycle; original_agenda=core_module.update_agenda
        calls=[]; ingestions=[]
        def cycle_spy(core,*args,**kwargs):
            calls.append(deepcopy(kwargs)); return original_cycle(core,*args,**kwargs)
        def agenda_spy(*args,**kwargs):
            decision=original_agenda(*args,**kwargs)
            decision['priority_change_supported_by_new_evidence']=True
            return decision
        original_ingest=public.ingest
        def ingest_spy(state,value):
            trace=original_ingest(state,value); ingestions.append((deepcopy(value),deepcopy(trace)))
            return trace
        with patch.object(AgentCore,'cycle',cycle_spy), patch.object(core_module,'update_agenda',agenda_spy), patch.object(core_module,'ingest_public_observation',ingest_spy):
            result=self.cycle(bundle('synthetic-2.json'))
        self.assertEqual(len(calls),2); self.assertTrue(calls[1]['_phase42_counterfactual'])
        self.assertEqual(calls[0]['copy_public_observations'],calls[1].get('copy_public_observations'))
        self.assertEqual(len(ingestions),2); self.assertEqual(ingestions[0],ingestions[1])
        for flag in ('strict_experiment_admission','planning_lab','_now_override'):
            self.assertEqual(calls[0][flag],calls[1][flag])
        self.assertTrue(calls[1]['_withhold_current_prediction_evidence'])
        self.assertIsNotNone(result['prediction_result'])


if __name__=='__main__': unittest.main()
