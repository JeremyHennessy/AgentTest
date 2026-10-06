"""Developer upgrade controls using real accepted-base producer/reviewer output."""
import json
import hashlib
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from agenttest.self_proposal import propose_self_change
from agenttest.proposal_review import review_change_proposal
from agenttest.state import StateStore


class NativeReviewUpgradeTests(unittest.TestCase):
    def old_state(self, ready=False):
        folder=Path(__file__).resolve().parent/'fixtures'/'native_waiting_review_upgrade'
        name='legacy_ready.json' if ready else 'legacy_waiting.json'
        provenance=json.loads((folder/'PROVENANCE.json').read_text())
        raw=(folder/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),provenance['files'][name]['sha256'])
        self.assertEqual(len(raw),provenance['files'][name]['bytes'])
        state=json.loads(raw)
        review=state['proposal_reviews'][0]
        self.assertEqual(review['review_version'],'proposal-review-v4')
        self.assertEqual(review['verdict'],'supported_problem')
        self.assertEqual(review['patch_authority'],'candidate_allowed')
        return state

    def test_upgrade_supersedes_false_authority_preserves_old_receipt_and_reload(self):
        state=self.old_state();old=deepcopy(state['proposal_reviews'][0]);proposal=state['change_proposals'][0]
        reused,created=propose_self_change(state)
        self.assertFalse(created);self.assertEqual(reused['id'],proposal['id'])
        with tempfile.TemporaryDirectory() as tmp:
            store=StateStore(Path(tmp)/'state.json');store.save(state);state=store.load();proposal=state['change_proposals'][0]
            fresh,created=review_change_proposal(state,proposal)
            self.assertTrue(created)
            self.assertEqual(fresh['verdict'],'no_problem_observed')
            self.assertEqual(fresh['patch_authority'],'none')
            self.assertEqual(proposal['status'],'closed_no_problem_observed')
            self.assertEqual(state['proposal_reviews'][0],old)
            self.assertEqual(len(state['proposal_reviews']),2)
            again,created=review_change_proposal(state,proposal)
            self.assertFalse(created);self.assertEqual(again,fresh)
            store.save(state);state=store.load();proposal=state['change_proposals'][0]
            again,created=review_change_proposal(state,proposal)
            self.assertFalse(created);self.assertEqual(again,fresh)
            self.assertEqual(state['proposal_reviews'][0],old)
            produced,_=propose_self_change(state)
            self.assertTrue(produced is None or produced['id']!=proposal['id'])

    def test_genuine_ready_authority_remains_cached_without_new_receipt(self):
        state=self.old_state(ready=True);before=deepcopy(state['proposal_reviews'])
        proposal=state['change_proposals'][0]
        reused,created=propose_self_change(state)
        self.assertFalse(created);self.assertEqual(reused,proposal)
        review,created=review_change_proposal(state,proposal)
        self.assertFalse(created);self.assertEqual(review['patch_authority'],'candidate_allowed')
        self.assertEqual(state['proposal_reviews'],before)

    def test_mixed_waiting_and_ready_work_retains_actual_closure_authority(self):
        state=self.old_state(ready=True)
        waiting=dict(state['experiments'][0],id='X_WAITING',readiness='awaiting_native_evidence')
        state['experiments'].append(waiting)
        before=deepcopy(state['proposal_reviews'])
        review,created=review_change_proposal(state,state['change_proposals'][0])
        self.assertFalse(created);self.assertEqual(review['patch_authority'],'candidate_allowed')
        self.assertEqual(state['proposal_reviews'],before)


if __name__=='__main__':unittest.main()
