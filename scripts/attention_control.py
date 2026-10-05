"""Explicit synthetic branch pipeline. Never evidence of natural drive behavior."""
import json
from copy import deepcopy
from pathlib import Path
from agenttest import public_observation as p
from agenttest.core import AgentCore
from agenttest.state import StateStore
from agenttest.agenda import update_agenda,_candidate_metrics
CLOCK='2026-10-05T21:20:00+00:00'
F=Path(__file__).resolve().parents[1]/'tests/fixtures'
def prepared(core,held_out=False):
 state=json.loads((F/'attention/control-state.json').read_bytes())
 traces=[]
 for index in (1,2):
  path=F/'attention'/f'held-out-{index}.json' if held_out else F/'public_observation'/f'synthetic-{index}.json'
  trace=p.ingest(state,p.load_bundle(path)); state['cycles']+=1; state['generation']=state['cycles']
  for pair in trace['pairs']:
   core._remember(state,state['cycles'],CLOCK,'native_inquiry_evidence',json.dumps(pair['evidence'],sort_keys=True),['native_evidence',pair['relation'],pair['evidence']['relation']['feature']])
   p.bind_evidence(state,trace['source'],pair['pair_id'],pair['relation'],state['episodes'][-1]['id'])
  trace['contracts']=p.admit(state,trace['source'],core._upsert_question); traces.append(deepcopy(trace))
 # Evidence binding itself accumulates concepts. This deliberately synthetic
 # branch control reapplies its preregistered concept precondition at the branch
 # boundary; primary ordinary cycles never reset or override their concepts.
 state['concept_counts']=json.loads((F/'attention/control-state.json').read_bytes())['concept_counts']
 return state,traces
def run(core,held_out,fallback):
 state,traces=prepared(core,held_out)
 blocked=core._blocked_question_ids(state)
 pool=[q for q in state['questions'] if q.get('status')=='open' and q['id'] not in blocked and (core._unallocated_prospective_question(state,q) if fallback else False)]
 text=core._generate_question(state,None,{'kind':'reduce_uncertainty'},None,strict_question_attention=True,copy_prospective_fallback=fallback)
 legacy=core._upsert_question(state,text)
 prospective=[q for q in state['questions'] if q.get('source')==p.SOURCE]
 before=[_candidate_metrics(state,q,legacy_question_id=legacy['id'],prior_thread=None) for q in prospective]
 decision=update_agenda(state,legacy_question=legacy,cycle=state['cycles'])
 winner=next(q for q in state['questions'] if q['id']==decision['selected']['question_id'])
 allocation=p.allocate_selected(state,winner,decision,CLOCK) if winner.get('source')==p.SOURCE else None
 row={'synthetic_branch_control':True,'held_out':held_out,'fallback':fallback,'accepted_records':traces,'fallback_reached':True,'pool':deepcopy(pool),'legacy':deepcopy(legacy),'candidate_metrics_before_allocation':before,'agenda_winner':deepcopy(winner),'agenda_decision':deepcopy(decision),'allocation':deepcopy(allocation),'tuple':[(q['times_selected'],int(q.get('last_selected_cycle',-1) or -1),q['created_cycle'],q['id']) for q in pool]}
 return row,state
