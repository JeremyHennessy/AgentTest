"""Developer cross-component controls on isolated synthetic histories only."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from agenttest import planning_lab
from agenttest.core import AgentCore
from agenttest.state import StateStore, initial_state
from agenttest.objective_identity import allocate_objective_decision_id
from agenttest.change_control import make_change_manifest
from agenttest.diagnostics import run_proposal_diagnostic
from agenttest.proposal_review import review_change_proposal
from scripts.phase42_experiment_routing_eval import evaluate_experiment_routes
from tests import test_planning_bootstrap_recovery as bootstrap
from tests import test_native_waiting_review_upgrade as governance


class CombinedComponentTests(unittest.TestCase):
    def test_recovered_bootstrap_then_retained_allocation_and_phase40_reload(self):
        state=initial_state()
        self.assertEqual(planning_lab.step_planning_lab(state)['status'],'waiting_for_model')
        bootstrap.add_source_actions(state,8)
        self.assertEqual(planning_lab.step_planning_lab(state)['action'],'east')
        lab=state['planning_lab'];source_rows=deepcopy(lab['transition_observations'])
        identities=[]
        for index in range(140):
            identifier=allocate_objective_decision_id(lab);identities.append(identifier)
            lab['objective_decisions'].append(dict(id=identifier,cycle=index+20,changed_choice=True,selected={'target':[0,0]}))
            del lab['objective_decisions'][:-128]
        self.assertEqual(len(set(identities)),140)
        self.assertEqual(lab['transition_observations'],source_rows)
        lab['position']=[0,0];lab['visit_counts']={'0,0':1}
        lab['goals']=[dict(id='PG_COMBINED',status='completed',target=[0,0],assigned_cycle=150,completed_cycle=151,
                           selection={'kind':'self_selected_bounded_objective','objective_decision_id':identities[-1]})]
        lab['active_goal_id']=lab['active_plan_id']=None
        lab['objective_realization_started_cycle']=100;lab['status']='goal_reached';state['cycles']=200
        with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as action:
            precommit=planning_lab.step_planning_lab(state)
            self.assertEqual(action.call_count,0)
        self.assertEqual(precommit['execution_kind'],'objective_information_precommit')
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json');store.save(state);state=store.load();lab=state['planning_lab']
            self.assertEqual(lab['next_objective_decision_index'],141)
            state['cycles']=201
            with patch.object(planning_lab,'apply_bounded_action',wraps=planning_lab.apply_bounded_action) as action:
                result=planning_lab.step_planning_lab(state)
            self.assertEqual(action.call_count,1)
            self.assertEqual(result['execution_kind'],'objective_information_realization')
            self.assertEqual(result['objective_decision_id'],identities[-1])
            self.assertEqual(len(lab['objective_realizations']),1)
            self.assertEqual(lab['transition_observations'][:len(source_rows)],source_rows)

    def test_independent_routing_validator_checks_real_core_returned_pairs(self):
        checked=owned=0
        with tempfile.TemporaryDirectory() as tmp:
            core=AgentCore(StateStore(Path(tmp)/'state.json'))
            observation=dict(branch='synthetic-combined',baseline_fingerprint='combined-fixed-code',tracked_files=10,
                             python_files=4,python_source_lines=100,test_files=1,working_tree_clean=True)
            for cycle,text in enumerate(['river rainfall','river rainfall','battery cold charge','compiler instruction latency'],1):
                result=core.cycle(text,observation=observation,cognition=False,planning_lab=True,
                                  _now_override=f'2026-10-06T03:0{cycle}:00+00:00')
                snapshot=core.store.load()
                audit=evaluate_experiment_routes([result],snapshot)
                self.assertEqual(audit['mismatch_count'],0)
                self.assertEqual(audit['unknown_count'],0)
                self.assertEqual(audit['raw_contradiction_count'],0)
                self.assertEqual(audit['telemetry_disagreement_count'],0)
                checked+=audit['checked_count'];owned+=audit['owned_count']
        self.assertGreater(checked,0);self.assertGreater(owned,0)

    def test_native_upgrade_and_stale_diagnostic_authority_preserve_history_on_reload(self):
        state=governance.NativeReviewUpgradeTests().old_state()
        native_proposal=state['change_proposals'][0];old_native_review=deepcopy(state['proposal_reviews'][0])
        state['self_model']['capabilities'].append('combined capability')
        proposal=make_change_manifest(state,title='Measure combined grounding',target_dimension='self_model',
            files=['src/agenttest/core.py'],hypothesis='Traceability can be measured.',expected_effect='Measure claims.',
            test_plan='Run grounding diagnostic.',falsification='No gap.',rollback='Revert.',evidence_refs=['E000001'])
        proposal['id']='M_COMBINED';state['change_proposals'].append(proposal)
        review_change_proposal(state,proposal)
        diagnostic,_=run_proposal_diagnostic(state,proposal);old_diagnostic=deepcopy(diagnostic)
        approved,_=review_change_proposal(state,proposal)
        self.assertEqual(approved['patch_authority'],'candidate_allowed')
        old_approval=deepcopy(approved)
        state['self_model']['capability_claims']['combined capability']={'status':'unverified','reason':'Not yet measured','evidence_refs':[]}
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json');store.save(state);state=store.load()
            native_proposal=state['change_proposals'][0];proposal=state['change_proposals'][1]
            native_review,created=review_change_proposal(state,native_proposal)
            self.assertTrue(created);self.assertEqual(native_review['patch_authority'],'none')
            stale_review,created=review_change_proposal(state,proposal)
            self.assertTrue(created);self.assertEqual(stale_review['patch_authority'],'diagnostic_only')
            self.assertEqual(stale_review['verdict'],'measurement_gap')
            current,created=run_proposal_diagnostic(state,proposal)
            self.assertTrue(created);self.assertEqual(current['outcome'],'grounded')
            final,_=review_change_proposal(state,proposal)
            self.assertEqual(final['verdict'],'no_problem_observed')
            self.assertEqual(state['proposal_reviews'][0],old_native_review)
            self.assertIn(old_approval,state['proposal_reviews'])
            self.assertEqual(state['proposal_diagnostics'][0],old_diagnostic)
            store.save(state);state=store.load()
            for proposal,expected in [(state['change_proposals'][0],native_review),(state['change_proposals'][1],final)]:
                cached,created=review_change_proposal(state,proposal)
                self.assertFalse(created);self.assertEqual(cached,expected)


if __name__=='__main__':unittest.main()
