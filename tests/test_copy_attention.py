"""Bounded attention controls; branch states are synthetic, never natural drive credit."""
from copy import deepcopy
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from agenttest import core as c,public_observation as p
from agenttest.core import AgentCore
from agenttest.state import StateStore,initial_state
from agenttest.semantic import question_has_active_experiment_path
from agenttest.agenda import update_agenda
spec=importlib.util.spec_from_file_location('attention_control',Path(__file__).resolve().parents[1]/'scripts/attention_control.py')
control=importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
F=Path(__file__).parent/'fixtures/public_observation'; CLOCK=control.CLOCK
class CopyAttentionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name); self.core=AgentCore(StateStore(self.root/'copy/ora.json'))
 def test_synthetic_original_and_heldout_controls(self):
  for held in (False,True):
   off,_=control.run(self.core,held,False); on,state=control.run(self.core,held,True)
   self.assertEqual(off['pool'],[]); self.assertEqual(len(on['pool']),8)
   expected=min(on['pool'],key=lambda q:(int(q.get('times_selected',0) or 0),int(q.get('last_selected_cycle',-1) or -1),int(q.get('created_cycle',0) or 0),q['id']))
   self.assertEqual(on['legacy']['id'],expected['id']); self.assertEqual(on['agenda_winner']['id'],expected['id'])
   self.assertIsNotNone(on['allocation']); self.assertIsNone(off['allocation'])
   for m in on['candidate_metrics_before_allocation']:
    self.assertFalse(m['active_experiment_path']); self.assertEqual(m['actionability_value'],0)
   self.assertEqual(sum(bool(x.get('public_observation_family')) for x in state['experiments']),1)
 def test_mutated_contracts_fail_closed_and_are_pure(self):
  original,_=control.prepared(self.core)
  original_q=next(q for q in original['questions'] if q.get('source')==p.SOURCE)
  fam=original_q['public_observation_family']
  for mutation in ('staleversion','wrongsource','missingevidence','exhaustion'):
   state=deepcopy(original); q=next(q for q in state['questions'] if q['id']==original_q['id'])
   entry=state[p.KEY]['families'][fam]
   if mutation=='staleversion': entry['version_id']='obsolete'
   elif mutation=='wrongsource': entry['source_id']='wrong-source'
   elif mutation=='missingevidence': state['episodes']=[e for e in state['episodes'] if e['id']!=q['source_evidence_refs'][0]]
   else:
    trace=p.ingest(state,p.load_bundle(F/'synthetic-3.json'))
    for pair in trace['pairs']:
     self.core._remember(state,state['cycles'],CLOCK,'native_inquiry_evidence',json.dumps(pair['evidence'],sort_keys=True),['native_evidence',pair['relation'],pair['evidence']['relation']['feature']])
     p.bind_evidence(state,trace['source'],pair['pair_id'],pair['relation'],state['episodes'][-1]['id'])
    p.admit(state,trace['source'],self.core._upsert_question)
   before=deepcopy(state)
   self.assertFalse(self.core._unallocated_prospective_question(state,q),mutation)
   self.assertEqual(state,before,mutation)
 def test_family_allocated_in_any_status_excluded(self):
  original,_=control.prepared(self.core); q=next(q for q in original['questions'] if q.get('source')==p.SOURCE)
  for status in ('proposed','resolved','parked_blocked'):
   state=deepcopy(original); state['experiments'].append({'id':'Xsynthetic','status':status,'public_observation_family':q['public_observation_family']})
   self.assertFalse(self.core._unallocated_prospective_question(state,q),status)
 def test_blocked_question_and_tuple_order_preserved(self):
  state,_=control.prepared(self.core); public=[q for q in state['questions'] if q.get('source')==p.SOURCE]
  blocked=self.core._blocked_question_ids(state)|{public[0]['id']}
  public[1]['times_selected']=2; public[2]['last_selected_cycle']=8
  remaining=[q for q in public if q['id'] not in blocked]
  chosen=self.core._least_selected_eligible_open_question(state,blocked,strict_question_attention=True,copy_prospective_fallback=True)
  expected=min(remaining,key=lambda q:(int(q.get('times_selected',0) or 0),int(q.get('last_selected_cycle',-1) or -1),int(q.get('created_cycle',0) or 0),q['id']))
  self.assertEqual(chosen['id'],expected['id']); self.assertNotEqual(chosen['id'],public[0]['id'])
  self.assertIsNone(self.core._least_selected_eligible_open_question(state,blocked,strict_question_attention=True))
 def test_nonselected_and_missing_current_receipt_never_allocate(self):
  state,_=control.prepared(self.core); legacy=self.core._upsert_question(state,'synthetic nonpublic legacy')
  decision=update_agenda(state,legacy_question=legacy,cycle=state['cycles'])
  q=next(q for q in state['questions'] if q.get('source')==p.SOURCE)
  before=deepcopy(state)
  self.assertIsNone(p.allocate_selected(state,q,decision,CLOCK)); self.assertEqual(state,before)
  text=self.core._generate_question(state,None,{'kind':'reduce_uncertainty'},None,strict_question_attention=True,copy_prospective_fallback=True)
  legacy=self.core._upsert_question(state,text); decision=update_agenda(state,legacy_question=legacy,cycle=state['cycles'])
  winner=next(q for q in state['questions'] if q['id']==decision['selected']['question_id'])
  before=deepcopy(state)
  for receipt in (None,deepcopy(decision)):
   self.assertIsNone(p.allocate_selected(state,winner,receipt,CLOCK)); self.assertEqual(state,before)
 def test_flags_reject_default_store_without_public_input(self):
  default=AgentCore(StateStore(Path('state/organism.json')))
  for flag in ('copy_early_prospective_admission','copy_prospective_fallback'):
   with patch.object(default.store,'load',return_value=initial_state()),patch.object(c,'load_public_bundle',side_effect=AssertionError('unexpected read')):
    with self.assertRaisesRegex(ValueError,'copied store'): default.cycle(**{flag:True})
 def test_registration_order_once_and_equal_pre_registration_computation(self):
  original=initial_state(); original['cycles']=10; original['agenda']['started_cycle']=1
  observation={'sensor':'fixture','observed_at':CLOCK,'git_available':False}
  self.core.store.save(original)
  self.core.cycle('autonomous heartbeat',observation,strict_experiment_admission=True,planning_lab=True,_now_override=CLOCK,copy_public_observations=F/'synthetic-1.json')
  start=self.core.store.load(); captures=[]
  for early,fallback in ((False,False),(True,False),(True,True)):
   self.core.store.save(deepcopy(start)); events=[]; values=[]
   admit=c.admit_public_observation; generate=AgentCore._generate_question
   def admission(s,*a,**kw):
    events.append('admit'); values.append(deepcopy({k:s.get(k) for k in ('metrics','drives','intentions')})); return admit(s,*a,**kw)
   def generation(obj,*a,**kw): events.append('generate'); return generate(obj,*a,**kw)
   with patch.object(c,'admit_public_observation',admission),patch.object(AgentCore,'_generate_question',generation):
    self.core.cycle('autonomous heartbeat',observation,strict_experiment_admission=True,planning_lab=True,_now_override=CLOCK,copy_public_observations=F/'synthetic-2.json',copy_early_prospective_admission=early,copy_prospective_fallback=fallback)
   self.assertEqual(events,['admit','generate'] if early else ['generate','admit']); self.assertEqual(len(values),1); captures.append(values[0])
  self.assertEqual(captures[0],captures[1]); self.assertEqual(captures[1],captures[2])
 def test_counterfactual_forwards_both_flags_and_identical_input(self):
  original=initial_state(); original['cycles']=10; original['agenda']['started_cycle']=1; self.core.store.save(original)
  observation={'sensor':'fixture','observed_at':CLOCK,'git_available':False}
  self.core.cycle('autonomous heartbeat',observation,strict_experiment_admission=True,planning_lab=True,_now_override=CLOCK,copy_public_observations=F/'synthetic-1.json')
  cycle=AgentCore.cycle; agenda=c.update_agenda; calls=[]; ingestions=[]; ingest=c.ingest_public_observation
  def cycle_spy(obj,*a,**kw): calls.append(deepcopy(kw)); return cycle(obj,*a,**kw)
  def agenda_spy(*a,**kw):
   d=agenda(*a,**kw)
   if d is not None: d['priority_change_supported_by_new_evidence']=True
   return d
  def ingest_spy(s,v):
   result=ingest(s,v); ingestions.append((deepcopy(v),deepcopy(result))); return result
  with patch.object(AgentCore,'cycle',cycle_spy),patch.object(c,'update_agenda',agenda_spy),patch.object(c,'ingest_public_observation',ingest_spy):
   self.core.cycle('autonomous heartbeat',observation,strict_experiment_admission=True,planning_lab=True,_now_override=CLOCK,copy_public_observations=F/'synthetic-2.json',copy_early_prospective_admission=True,copy_prospective_fallback=True)
  self.assertEqual(len(calls),2); self.assertTrue(calls[1]['_phase42_counterfactual'])
  for flag in ('copy_public_observations','copy_early_prospective_admission','copy_prospective_fallback','strict_experiment_admission','planning_lab','_now_override'): self.assertEqual(calls[0][flag],calls[1][flag])
  self.assertEqual(ingestions[0],ingestions[1])
if __name__=='__main__': unittest.main()
