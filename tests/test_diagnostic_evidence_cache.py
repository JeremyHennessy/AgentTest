"""Developer evidence-sensitive cache controls for all three proposal evaluators."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from agenttest import diagnostics
from agenttest.change_control import make_change_manifest
from agenttest.proposal_review import review_change_proposal
from agenttest.state import initial_state, StateStore

TEXTS=['How does rainfall alter river water level?', 'Which battery chemistry tolerates cold charging?',
       'What bird migration route crosses the northern coast?', 'How do compiler optimizations affect instruction latency?']

def fixture(target):
    state=initial_state();state['cycles']=10
    state['environment_snapshots']=[{'baseline_fingerprint':'fixed-code'}]
    state['questions']=[{'id':'Q1','text':TEXTS[0]}]
    state['self_model']['capabilities']=['test capability']
    state['self_model']['capability_claims']={}
    proposal=make_change_manifest(state,title='Measure diagnostic evidence',target_dimension=target,
        files=['src/agenttest/core.py'],hypothesis='A controlled diagnostic can identify a specific defect.',
        expected_effect='Measure existing evidence.',test_plan='Run controlled diagnostic.',
        falsification='No demonstrated defect.',rollback='Revert.',evidence_refs=['Q1'])
    proposal['id']='M1';state['change_proposals']=[proposal]
    review_change_proposal(state,proposal)
    return state,proposal


class DiagnosticEvidenceCacheTests(unittest.TestCase):
    def test_one_to_four_questions_preserves_old_and_refreshes_review(self):
        state,proposal=fixture('open_endedness')
        first,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(first['outcome'],'insufficient_data')
        old=deepcopy(first);review_change_proposal(state,proposal)
        state['questions'].extend(dict(id=f'Q{i+1}',text=text) for i,text in enumerate(TEXTS[1:],1))
        stale_review,created=review_change_proposal(state,proposal)
        self.assertTrue(created)
        second,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(second['outcome'],'diverse')
        self.assertEqual(state['proposal_diagnostics'][0],old)
        final,_=review_change_proposal(state,proposal)
        self.assertEqual(final['patch_authority'],'none')
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json');store.save(state);state=store.load();proposal=state['change_proposals'][0]
            cached,created=diagnostics.run_proposal_diagnostic(state,proposal)
            self.assertFalse(created);self.assertEqual(cached,second)
            cached,created=review_change_proposal(state,proposal)
            self.assertFalse(created);self.assertEqual(cached,final)

    def test_inquiry_relevant_values_refresh_but_metadata_does_not(self):
        state,proposal=fixture('open_endedness')
        state['questions']=[dict(id=f'Q{i+1}',text=text) for i,text in enumerate(TEXTS)]
        state['metrics']['open_endedness']=0.4
        first,_=diagnostics.run_proposal_diagnostic(state,proposal)
        review_change_proposal(state,proposal)
        self.assertEqual(proposal['status'],'closed_no_problem_observed')
        state['updated_at']='later';state['metrics']['agency']=0.99
        state['questions'][0].update(status='answered',times_selected=99,created_at='later')
        cached,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertFalse(created);self.assertEqual(cached,first)
        for row in state['questions']:row['text']='Why does repeated rainfall alter river water level?'
        second,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(second['outcome'],'paraphrase_churn')
        review,_=review_change_proposal(state,proposal)
        self.assertEqual(review['patch_authority'],'candidate_allowed')
        for key,value in [('cycles',20),('metric',0.9),('identity','Q_CHANGED')]:
            if key=='cycles':state['cycles']=value
            elif key=='metric':state['metrics']['open_endedness']=value
            else:state['questions'][0]['id']=value
            _,created=diagnostics.run_proposal_diagnostic(state,proposal)
            self.assertTrue(created)

    def test_self_model_claim_and_referenced_evidence_changes_refresh(self):
        state,proposal=fixture('self_model')
        first,_=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertEqual(first['outcome'],'grounding_gap')
        state['self_model']['capability_claims']['test capability']={'status':'unverified','reason':'Not yet measured','evidence_refs':[]}
        second,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(second['outcome'],'grounded')
        review_change_proposal(state,proposal)
        state['cycles']+=1;state['episodes'].append({'id':'E_UNRELATED','content':'irrelevant','time':'now'})
        state['self_model']['capability_claims']['unlisted claim']={'status':'verified','evidence_refs':['UNKNOWN']}
        cached,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertFalse(created);self.assertEqual(cached,second)
        claim=state['self_model']['capability_claims']['test capability']
        claim.update(status='verified',evidence_refs=['E_CITED'])
        third,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(third['outcome'],'grounding_gap')
        state['episodes'].append({'id':'E_CITED','content':'measured'})
        fourth,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(fourth['outcome'],'grounded')
        state['episodes']=[row for row in state['episodes'] if row['id']!='E_CITED']
        fifth,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertFalse(created);self.assertEqual(fifth,third)
        self.assertEqual(state['proposal_diagnostics'][0],first)

    def test_replay_has_no_live_evidence_input_but_code_and_version_still_matter(self):
        state,proposal=fixture('reproducibility')
        with patch.object(diagnostics,'compare_replays',return_value={'outcome':'stable'}) as evaluator:
            first,_=diagnostics.run_proposal_diagnostic(state,proposal)
            review_change_proposal(state,proposal)
            state['cycles']+=10;state['questions'].append({'id':'Q_IRRELEVANT','text':'New unrelated inquiry'})
            state['updated_at']='later'
            cached,created=diagnostics.run_proposal_diagnostic(state,proposal)
            self.assertFalse(created);self.assertEqual(cached,first);self.assertEqual(evaluator.call_count,1)
            state['environment_snapshots'].append({'baseline_fingerprint':'changed-code'})
            evaluator.return_value={'outcome':'divergent'}
            second,created=diagnostics.run_proposal_diagnostic(state,proposal)
            self.assertTrue(created);self.assertEqual(second['outcome'],'divergent')
            with patch.object(diagnostics,'REPLAY_VERSION','developer-version-control'):
                _,created=diagnostics.run_proposal_diagnostic(state,proposal)
                self.assertTrue(created)

    def test_legacy_unverifiable_receipts_preserved_but_not_current_authority(self):
        for target in ('open_endedness','self_model','reproducibility'):
            with self.subTest(target=target):
                state,proposal=fixture(target)
                with patch.object(diagnostics,'compare_replays',return_value={'outcome':'divergent'}):
                    diagnostic,_=diagnostics.run_proposal_diagnostic(state,proposal)
                    diagnostic.pop('input_fingerprint')
                    old=deepcopy(diagnostic)
                    review,_=review_change_proposal(state,proposal)
                    self.assertNotEqual(review['patch_authority'],'candidate_allowed')
                    fresh,created=diagnostics.run_proposal_diagnostic(state,proposal)
                self.assertTrue(created);self.assertNotEqual(fresh['id'],old['id'])
                self.assertEqual(state['proposal_diagnostics'][0],old)

    def test_completed_system_evidence_matters_only_when_cited(self):
        state,proposal=fixture('self_model')
        state['self_model']['capability_claims']['test capability']={'status':'verified','evidence_refs':['SD_CITED']}
        first,_=diagnostics.run_proposal_diagnostic(state,proposal)
        state['system_diagnostics']=[{'id':'SD_CITED','status':'pending'}]
        cached,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertFalse(created);self.assertEqual(cached,first)
        state['system_diagnostics'][0]['status']='completed'
        fresh,created=diagnostics.run_proposal_diagnostic(state,proposal)
        self.assertTrue(created);self.assertEqual(fresh['outcome'],'grounded')

    def test_version_and_code_identity_invalidate_every_family(self):
        for target,version in [('open_endedness','INQUIRY_VERSION'),('self_model','SELF_MODEL_VERSION'),('reproducibility','REPLAY_VERSION')]:
            with self.subTest(target=target), patch.object(diagnostics,'compare_replays',return_value={'outcome':'stable'}):
                state,proposal=fixture(target)
                old,_=diagnostics.run_proposal_diagnostic(state,proposal)
                saved=deepcopy(old)
                state['environment_snapshots'].append({'baseline_fingerprint':'new-code'})
                current,created=diagnostics.run_proposal_diagnostic(state,proposal)
                self.assertTrue(created)
                with patch.object(diagnostics,version,'developer-version-control'):
                    versioned,created=diagnostics.run_proposal_diagnostic(state,proposal)
                    self.assertTrue(created)
                    cached,created=diagnostics.run_proposal_diagnostic(state,proposal)
                    self.assertFalse(created);self.assertEqual(cached,versioned)
                self.assertEqual(state['proposal_diagnostics'][0],saved)


if __name__=='__main__':unittest.main()
