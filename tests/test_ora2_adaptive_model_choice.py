"""Synthetic-only verification of pre-observation adaptive expert choice."""
from collections import deque
from copy import deepcopy
import unittest

from ora2.adaptive_model_choice import (
    AdaptiveModel, EXPERTS, WINDOW, StudyInvalid, proper_distribution,
    weights_from_previous_losses,
)
from ora2.action_effect_transfer import validate_rows, predict


def example(before, action, after, cycle, blocked=False, *, world='bounded-stateful-world-v1', source_id=None):
    return {'before': list(before), 'action': action, 'after': list(after),
            'cycle': cycle, 'source': 'synthetic', 'source_id': source_id or f'S{cycle}',
            'world_version': world, 'blocked': blocked}


def p(distribution, after):
    return next(r['p'] for r in distribution if r['after'] == list(after))


class AdaptiveChoiceTests(unittest.TestCase):
    def test_initial_weights_are_equal_and_all_forecasts_normalize(self):
        s=AdaptiveModel()
        forecast=s.preview((0,0), 'aqua')
        for name in EXPERTS:
            self.assertAlmostEqual(forecast['model_weights'][name],1/3)
        for d in forecast['distributions'].values():
            self.assertAlmostEqual(sum(row['p'] for row in d),1.)
            self.assertEqual(len(d),25)
        self.assertNotIn('after', forecast)
        with self.assertRaisesRegex(StudyInvalid,'pending'):
            s.preview((0,0),'aqua')

    def test_update_requires_identity_action_and_correct_sequence(self):
        s=AdaptiveModel()
        with self.assertRaisesRegex(StudyInvalid,'no pre-outcome'):
            s.observe(example((0,0),'t',(0,1),1))
        s.preview((0,0),'t')
        with self.assertRaisesRegex(StudyInvalid,'attributed'):
            s.observe(example((0,0),'different',(0,1),1))
        self.assertEqual(s.rows,0)
        s.observe(example((0,0),'t',(0,1),1))
        s.preview((0,0),'t')
        with self.assertRaisesRegex(StudyInvalid,'duplicate'):
            s.observe(example((0,0),'t',(0,1),1))
        self.assertEqual(s.rows,1)

    def test_prospective_displacement_learns_and_is_name_independent(self):
        s=AdaptiveModel()
        for i, before in enumerate(((0,0),(1,0)),1):
            s.preview(before,'violet')
            s.observe(example(before,'violet',(before[0],-1),i))
        predicted=s.preview((2,0),'violet')
        self.assertGreater(p(predicted['distributions']['shared_effect'],(2,-1)),0.9)
        self.assertAlmostEqual(sum(predicted['model_weights'].values()),1.)
        self.assertEqual(len(s.identities),2)
        s2=AdaptiveModel()
        for i, before in enumerate(((0,0),(1,0)),1):
            s2.preview(before,'turquoise')
            s2.observe(example(before,'turquoise',(before[0],-1),i))
        other=s2.preview((2,0),'turquoise')
        self.assertEqual(predicted['distributions'],other['distributions'])

    def test_global_matches_the_existing_frozen_spatial_predictor(self):
        events=[example((0,0),'v',(1,0),1),example((1,0),'v',(2,0),2),
                example((0,0),'v',(0,0),3,True)]
        s=AdaptiveModel()
        for row in events:
            s.preview(row['before'],row['action']);s.observe(row)
        f=s.preview((2,0),'v')
        expected=predict(validate_rows(events),(2,0),'v',model='shared_effect')
        self.assertEqual([v['p'] for v in f['distributions']['shared_effect']],
                         [expected[pos] for pos in sorted(expected)])
        self.assertGreater(p(f['distributions']['exact_context'],(0,0)),0)

    def test_local_exception_hierarchy_retains_certain_global_prior(self):
        s=AdaptiveModel()
        events=[example((0,0),'a',(1,0),1),example((1,0),'a',(2,0),2),
                example((-1,0),'a',(-1,0),3,True)]
        for row in events:
            s.preview(row['before'],row['action']);s.observe(row)
        f=s.preview((-1,0),'a')
        loc=p(f['distributions']['exact_context'],(-1,0))
        glob=p(f['distributions']['shared_effect'],(-1,0))
        hier=p(f['distributions']['local_exception'],(-1,0))
        self.assertAlmostEqual(hier,(2/3)*glob+(1/3)*loc)
        self.assertGreater(hier,glob)

    def test_weights_adapt_and_forget_old_loss_without_future_data(self):
        scores={name:deque(maxlen=WINDOW) for name in EXPERTS}
        for i in range(64):
            scores['shared_effect'].append(0.01)
            scores['exact_context'].append(5.0)
            scores['local_exception'].append(2.0)
        w=weights_from_previous_losses(scores)
        self.assertGreater(w['shared_effect'],0.95)
        for i in range(64):
            scores['shared_effect'].append(5.0)
            scores['exact_context'].append(0.01)
            scores['local_exception'].append(2.0)
        w2=weights_from_previous_losses(scores)
        self.assertGreater(w2['exact_context'],0.95)
        self.assertLess(w2['shared_effect'],0.05)
        self.assertTrue(all(x>=.06/3 for x in w2.values()))

    def test_nan_or_missing_loss_is_rejected(self):
        with self.assertRaises(StudyInvalid):
            weights_from_previous_losses({'shared_effect':[], 'exact_context':[]})
        d={name:deque([1.0]) for name in EXPERTS}
        d['exact_context'][0]=float('nan')
        with self.assertRaises(StudyInvalid):
            weights_from_previous_losses(d)

    def test_cross_world_and_out_of_order_rejected_with_no_mutation(self):
        s=AdaptiveModel()
        s.preview((0,0),'a')
        with self.assertRaisesRegex(StudyInvalid,'world'):
            s.observe(example((0,0),'a',(0,0),1,world='other-world'))
        self.assertEqual(s.rows,0)
        s.observe(example((0,0),'a',(0,0),2))
        s.preview((0,0),'a')
        with self.assertRaisesRegex(StudyInvalid,'out-of-order'):
            s.observe(example((0,0),'a',(0,0),1))
        self.assertEqual(s.rows,1)

    def test_replay_retains_exact_chain_and_pre_action_forecasts(self):
        series=[example((0,0),'a',(1,0),1),example((1,0),'a',(2,0),2),
                example((2,0),'a',(2,0),3,True),example((2,0),'b',(2,-1),4)]
        outputs=[]
        for trial in range(2):
            s=AdaptiveModel()
            rec=[]
            for row in deepcopy(series):
                f=s.preview(row['before'],row['action'])
                self.assertEqual(f['history_length'],len(rec))
                rec.append(s.observe(row))
            outputs.append((s.chain,rec))
        self.assertEqual(outputs[0],outputs[1])
        self.assertEqual(len(outputs[0][1]),4)

    def test_invalid_distribution_does_not_pass_admission(self):
        from ora2.adaptive_model_choice import uniform
        dist=uniform();dist[(0,0)]=0.5
        with self.assertRaisesRegex(StudyInvalid,'distribution'):
            proper_distribution(dist)


if __name__=='__main__':
    unittest.main()
