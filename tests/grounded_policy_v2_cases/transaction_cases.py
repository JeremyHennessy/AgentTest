"""Tiny declared synthetic invariants. Every fixture has <=8 simulator calls.

Not the scientific32-anchor corpus, neutral64-step streams, or historical data.
Two setup moves make a north cohort; its retained blocked outcome is a wiring
control only, never evidence of learning effectiveness or useful exploration.
"""
from __future__ import annotations
import json,os,sys,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments'))
from grounded_policy_v2 import executive as module
from grounded_policy_v2.executive import GroundedExecutive,validate_capsule,_view
from grounded_policy_v2.contracts import (Conflict,Capacity,canonical,digest,encoded,strict_json,profile,COMPLETION_RESERVE,INTERPRETATION_RESERVE,
 T2_GROWTH_BOUND,T3_GROWTH_BOUND,RECORD_CAP)
from grounded_policy_v2.views import validate_prefix,discovery_and_common
from open_object_world_challenge import initial_world,observe_world,transition
STATS={'setup_transitions':0,'owned_transition_invocations':0,'durable_outcomes':0,'fixtures':0}
REAL_TRANSITION=module.transition

def counted_transition(*args,**kwargs):
    STATS['owned_transition_invocations']+=1
    return REAL_TRANSITION(*args,**kwargs)

class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='grounded-v2-invariant-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.research=self.root/'research';self.research.mkdir()
        self.path=self.research/'capsule.json';self.calls=0
        patcher=patch.object(module,'transition',side_effect=counted_transition);patcher.start();self.addCleanup(patcher.stop)
    def sources(self,name='input',commands=('north','north')):
        STATS['fixtures']+=1
        base=self.root/name;base.mkdir();w=initial_world(1);frames=[dict(observation=observe_world(w),receipt=None)]
        for action in commands:
            w,r=transition(w,{'action':action},cycle=w['cycle']+1)
            frames.append(dict(observation=observe_world(w),receipt=r));STATS['setup_transitions']+=1;self.calls+=1
        paths={k:base/(k+'.json') for k in ('ora','world','observations')}
        for k,v in dict(ora={},world=w,observations=frames).items():paths[k].write_bytes(canonical(v))
        return paths
    def create(self,*,paths=None,**kwargs):
        return GroundedExecutive.create(self.path,research_dir=self.research,source_paths=paths or self.sources(),discovery_count=kwargs.pop('discovery_count',2),enabled=True,**kwargs)
    def prepare(self,**kwargs):
        e=self.create(**kwargs);d=e.select_next(0);self.assertEqual(d['status'],'selected');return e,d
    def finish(self,e):
        s=e.read();o=e.execute(s['attempts'][-1]['id'],s['revision']);STATS['durable_outcomes']+=1
        b=e.interpret(o['id'],e.read()['revision']);return o,b
    def unchanged(self,e,fn,errors=(ValueError,OSError,TypeError)):
        before=self.path.read_bytes()
        with self.assertRaises(errors):fn()
        self.assertEqual(before,self.path.read_bytes())
    def reopen(self):return GroundedExecutive(self.path,research_dir=self.research,enabled=True)
    def test_default_off_and_creation_only_pins(self):
        sources=self.sources()
        for kw in ({},{'enabled':True,'selection_backend':'Core'},{'enabled':True,'source_id':'unknown'},{'enabled':True,'evidence_mode':'other'}):
            with self.assertRaises(ValueError):GroundedExecutive.create(self.path,research_dir=self.research,source_paths=sources,discovery_count=2,**kw)
        e=self.create(paths=sources)
        self.assertEqual(e.read()['identity']['selection_backend'],'grounded_policy_v2')
        self.unchanged(e,lambda:e.select_next(0,selection_backend='other'))
        self.unchanged(e,lambda:e.select_next(0,winner='north'))
    def test_owned_blocked_two_decision_restart_and_no_replay(self):
        e,d=self.prepare();self.assertEqual(d['command'],{'action':'north'})
        s=e.read();self.assertEqual(s['reserve'],COMPLETION_RESERVE);a=s['attempts'][0]['id']
        e=self.reopen();o=e.execute(a,1);STATS['durable_outcomes']+=1
        self.assertTrue(o['receipt']['blocked']);self.assertEqual(e.read()['reserve'],INTERPRETATION_RESERVE)
        self.unchanged(e,lambda:e.select_next(2))
        with patch.object(module,'transition',side_effect=AssertionError('replay')):self.assertEqual(e.execute(a,2),o)
        e=self.reopen();b=e.interpret(o['id'],2)
        self.assertEqual(b['reason'],'case_local_discrimination_only');self.assertEqual(e.read()['reserve'],0)
        with patch.object(module,'_interpretation',side_effect=module._interpretation):self.assertEqual(e.interpret(o['id'],3),b)
        d2=e.select_next(3);self.assertNotEqual(d['owner_id'],d2['owner_id']);self.finish(e)
        self.unchanged(e,lambda:e.select_next(6));self.assertEqual(len(e.read()['outcomes']),2)
    def test_stage_two_mask_is_materialized_and_first_lifecycle_identical(self):
        e=self.create();d=e.select_next(0);o,b=self.finish(e);s=e.read()
        _,retained,mask,_=_view(s,2,s['world'],s['outcomes'],s['beliefs'],s['decisions'])
        copy=deepcopy(s);copy['identity']['evidence_mode']='withhold_first'
        _,withheld,wmask,_=_view(copy,2,copy['world'],copy['outcomes'],copy['beliefs'],copy['decisions'])
        self.assertEqual(retained['lifecycle'],withheld['lifecycle'])
        self.assertEqual(retained['context'],withheld['context']);self.assertEqual(retained['cohort'],withheld['cohort'])
        self.assertEqual(len(retained['evidence']),1);self.assertEqual(withheld['evidence'],[])
        text=canonical(withheld).decode()
        for forbidden in (o['id'],o['receipt']['id'],d['id'],d['owner_id'],b['id'],str(self.path),'outcome_hash','posterior','mask'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(wmask['excluded'],[digest(retained['evidence'][0])])
        self.assertNotIn('excluded',withheld)
        # Separate explicit-create branch, same first internally selected action.
        other=self.research/'other.json'
        w=GroundedExecutive.create(other,research_dir=self.research,source_paths=self.sources('otherinput'),discovery_count=2,enabled=True,evidence_mode='withhold_first')
        wd=w.select_next(0);self.assertEqual(wd['body'],d['body']);wo,wb=self.finish(w)
        self.assertEqual(wo['receipt'],o['receipt']);self.assertEqual(wb['evaluations'],b['evaluations'])
        rd2=e.select_next(3);wd2=w.select_next(3)
        self.assertNotEqual(rd2['body']['menu'][0]['posterior'],wd2['body']['menu'][0]['posterior'])
        self.assertEqual(len(e.read()['outcomes']),len(w.read()['outcomes']))
    def test_changed_context_does_not_reuse_first_update(self):
        e=self.create(paths=self.sources(commands=('north','north','south')))
        d=e.select_next(0);o,b=self.finish(e)
        self.assertTrue(o['receipt']['success'])
        s=e.read();_,view,_,_=_view(s,2,s['world'],s['outcomes'],s['beliefs'],s['decisions'])
        retained=module.policy.evaluate(view['cohort'],view['context'],view['evidence'])
        withheld=module.policy.evaluate(view['cohort'],view['context'],view['evidence'][:-1])
        self.assertEqual(retained,withheld)
    def test_null_is_budgeted_and_no_attempt_fills_slot(self):
        e=self.create(paths=self.sources(commands=()),discovery_count=0)
        d=e.select_next(0);self.assertEqual(d['status'],'policy_null');self.assertIsNone(d['owner_id'])
        second=e.select_next(1);self.assertEqual(second['body'],d['body']);self.assertEqual(e.read()['attempts'],[])
        self.unchanged(e,lambda:e.select_next(2))
    def test_cancellation_is_terminal_and_cannot_mask_uncompleted_owner(self):
        e,d=self.prepare();a=e.read()['attempts'][0]['id'];e.cancel(a,1)
        self.unchanged(e,lambda:e.execute(a,2));self.unchanged(e,lambda:e.select_next(2))
        self.assertEqual(e.read()['world']['cycle'],2)
    def test_stale_revision_foreign_attempt_and_caller_receipt_reject(self):
        e,d=self.prepare();a=e.read()['attempts'][0]['id']
        for fn in (lambda:e.execute(a,0),lambda:e.execute('foreign',1),lambda:e.execute(a,True),lambda:e.execute(a,1.0),lambda:e.interpret('invented',1),lambda:e.select_next(1,receipt=d)):
            self.unchanged(e,fn)
    def test_backend_runs_once_and_verifier_cannot_select(self):
        e=self.create();real=module.policy.evaluate
        with patch.object(module.policy,'evaluate',wraps=real) as call:
            e.select_next(0);self.assertEqual(call.call_count,1);e.read();self.assertEqual(call.call_count,1)
        with patch.object(module.policy,'evaluate',side_effect=AssertionError('backend replay')):self.reopen()
    def test_duplicate_delivery_same_cohort_and_unique_discovery_boundary(self):
        paths=self.sources();frames=json.loads(paths['observations'].read_text());frames.insert(2,deepcopy(frames[1]));paths['observations'].write_bytes(canonical(frames))
        e=self.create(paths=paths);self.assertEqual(len(e.read()['frames']),3)
        D,U=discovery_and_common(e.read()['frames'],2);self.assertEqual(len(D),2);self.assertEqual(U,[])
        frames[2]['observation']['visible_entities'][0]['appearance']='changed';paths['observations'].write_bytes(canonical(frames))
        self.unchanged(e,lambda:self.reopen())
    def test_source_drift_and_unknown_source_substitution_reject(self):
        e,d=self.prepare();clean=self.path.read_bytes();s=e.read();s['identity']['adapter']['source_id']='other';s['identity_hash']=digest(s['identity']);self.path.write_bytes(encoded(s))
        with self.assertRaises(ValueError):self.reopen()
        self.path.write_bytes(clean);source=Path(e.read()['identity']['source_inputs']['observations']['path']);source.write_bytes(source.read_bytes()+b' ')
        self.unchanged(e,lambda:self.reopen())
    def test_full_menu_forgery_and_case_immutability_reject_before_mutation(self):
        e,d=self.prepare();original=self.path.read_bytes()
        mutations=[lambda s:s['decisions'][0]['body']['menu'].pop(),lambda s:s['decisions'][0]['body'].update(selected_action='east'),
         lambda s:s['decisions'][0]['cases'][0]['hypotheses'][0].update(position=[2,2]),
         lambda s:s['attempts'][0].update(owner_id='foreign'),lambda s:s['attempts'][0]['command'].update(action='east'),
         lambda s:s['decisions'][0]['anchor'].update(previous_belief_hash='0'*64),lambda s:s['cohort']['actions'][0]['models'].pop()]
        for mutate in mutations:
            s=strict_json(original);mutate(s);self.path.write_bytes(encoded(s));bad=self.path.read_bytes()
            with self.assertRaises((ValueError,KeyError,IndexError)):self.reopen()
            self.assertEqual(bad,self.path.read_bytes());self.path.write_bytes(original)
    def test_latest_world_and_belief_anchors_reject(self):
        e,d=self.prepare();o,b=self.finish(e);e.select_next(3);self.finish(e);original=self.path.read_bytes()
        for mutate in (lambda s:s['world'].update(position=[-2,0]),lambda s:s['beliefs'][-1].update(predecessor=None),
                       lambda s:s['beliefs'][0]['evaluations'][0].update(verdict='supported'),lambda s:s['outcomes'][0]['receipt'].update(before=[-2,0])):
            s=strict_json(original);mutate(s);self.path.write_bytes(encoded(s))
            with self.assertRaises(ValueError):self.reopen()
            self.path.write_bytes(original)
    def test_strict_json_scalars_and_duplicate_keys(self):
        with self.assertRaises(ValueError):strict_json('{"x":1,"x":1}')
        with self.assertRaises(ValueError):strict_json('{"x":NaN}')
        e,d=self.prepare();original=self.path.read_bytes()
        for field in ('revision','reserve'):
            for value in (True,1.0):
                s=strict_json(original);s[field]=value;self.path.write_bytes(encoded(s))
                with self.assertRaises(ValueError):self.reopen()
        self.path.write_bytes(original)
    def test_action_capacity_null_has_no_runner_up(self):
        e=self.create(limits=profile(max_actions=0));d=e.select_next(0)
        self.assertEqual(d['status'],'capacity_null');self.assertEqual(d['body']['selected_action'],'north')
        self.assertIsNone(d['owner_id']);self.assertEqual(e.read()['attempts'],[])
    def test_byte_capacity_and_reserved_completion_bounds(self):
        e,d=self.prepare();before=e.read();before_bytes=len(encoded(before))
        self.assertLessEqual(before_bytes+COMPLETION_RESERVE,before['identity']['profile']['max_bytes'])
        o=e.execute(before['attempts'][0]['id'],1);STATS['durable_outcomes']+=1;after=e.read()
        self.assertLessEqual(len(encoded(after))-before_bytes,T2_GROWTH_BOUND)
        size=len(encoded(after));e.interpret(o['id'],2);self.assertLessEqual(len(encoded(e.read()))-size,T3_GROWTH_BOUND)
        # Four maximal retained records are covered; remaining metadata margin.
        self.assertLess(4*RECORD_CAP+INTERPRETATION_RESERVE+16_384,COMPLETION_RESERVE)
    def test_exact_serialized_selected_boundary_and_byte_null(self):
        e=self.create();state=e.read()
        _,view,mask,anchor=_view(state,1,state['world'],[],[],[])
        body=module.policy.evaluate(view['cohort'],view['context'],view['evidence'])
        # Pure size oracle, not a copied/resealed capsule or executable branch.
        cap=1_000_000
        for _ in range(8):
            candidate=deepcopy(state);candidate['identity']['profile']['max_bytes']=cap
            candidate['identity_hash']=digest(candidate['identity'])
            decision=module._decision(candidate,1,body,view,mask,anchor,1,'selected')
            candidate['decisions'].append(decision);candidate['attempts'].append(module._attempt(candidate,decision))
            candidate['reserve']=COMPLETION_RESERVE;module._event(candidate,'select',decision['id'],decision['hash'])
            next_cap=len(encoded(candidate))+COMPLETION_RESERVE
            if next_cap==cap:break
            cap=next_cap
        for index,limit in enumerate((cap,cap-1)):
            # Equal-length output name preserves the proven canonical-size boundary.
            path=self.research/('capsule'+str(index)+'.jso')
            self.assertEqual(len(str(path)),len(str(self.path)))
            x=GroundedExecutive.create(path,research_dir=self.research,source_paths={k:Path(v['path']) for k,v in state['identity']['source_inputs'].items()},
                discovery_count=2,enabled=True,limits=profile(max_bytes=limit))
            d=x.select_next(0)
            self.assertEqual(d['status'],'selected' if index==0 else 'capacity_null')
            self.assertLessEqual(len(path.read_bytes())+x.read()['reserve'],limit)
            if index==0:self.finish(x)
    def test_maximal_receipt_completion_and_oversized_rejection(self):
        e,d=self.prepare();a=e.read()['attempts'][0]['id'];real=module.transition
        def padded(*args,**kwargs):
            world,receipt=real(*args,**kwargs)
            receipt['observed_effects']=['x']
            overhead=len(canonical(receipt))-1
            receipt['observed_effects']=['x'*(RECORD_CAP-overhead)]
            self.assertEqual(len(canonical(receipt)),RECORD_CAP)
            world['history'][-1]=deepcopy(receipt)
            return world,receipt
        with patch.object(module,'transition',side_effect=padded):o=e.execute(a,1)
        STATS['durable_outcomes']+=1
        self.assertEqual(len(canonical(o['receipt'])),RECORD_CAP);e.interpret(o['id'],2)
        # Another fresh two-move fixture tests overflow-before-persistence.
        path=self.research/'too-large.json'
        x=GroundedExecutive.create(path,research_dir=self.research,source_paths=self.sources('overflow'),discovery_count=2,enabled=True)
        x.select_next(0);before=path.read_bytes()
        def oversized(*args,**kwargs):
            world,receipt=real(*args,**kwargs);receipt['observed_effects']=['x'*RECORD_CAP]
            world['history'][-1]=deepcopy(receipt);return world,receipt
        with patch.object(module,'transition',side_effect=oversized),self.assertRaises(ValueError):
            x.execute(x.read()['attempts'][0]['id'],1)
        self.assertEqual(path.read_bytes(),before)
    def test_forged_capacity_null_is_not_an_authorized_substitute(self):
        e,d=self.prepare();original=self.path.read_bytes();s=e.read()
        d=s['decisions'][0];d['status']='capacity_null'
        for key in ('owner_id','experiment_id','command','case_hash'):d[key]=None
        d['hash']=module._hash(d);s['attempts']=[];s['reserve']=0
        s['events'][0]['result_hash']=d['hash'];s['events'][0]['hash']=module._hash(s['events'][0])
        self.path.write_bytes(encoded(s))
        with self.assertRaises(ValueError):self.reopen()
        self.path.write_bytes(original)
    def test_source_path_alias_and_capsule_relocation_refused(self):
        sources=self.sources();alias=self.root/'alias.json';os.link(sources['ora'],alias);sources['ora']=alias
        with self.assertRaises(ValueError):self.create(paths=sources)
        os.unlink(alias);sources['ora']=self.root/'input/ora.json';e=self.create(paths=sources)
        elsewhere=self.research/'elsewhere.json';elsewhere.write_bytes(self.path.read_bytes())
        os.link(self.path.with_name(self.path.name+'.lock'),elsewhere.with_name(elsewhere.name+'.lock'))
        with self.assertRaises(ValueError):GroundedExecutive(elsewhere,research_dir=self.research,enabled=True)
    def test_pure_transition_failure_leaves_world_unchanged(self):
        e,d=self.prepare();a=e.read()['attempts'][0]['id']
        with patch.object(module,'transition',side_effect=RuntimeError('synthetic precommit failure')):
            self.unchanged(e,lambda:e.execute(a,1),errors=RuntimeError)
        self.assertEqual(e.read()['attempts'][0]['status'],'prepared')
    def test_unknown_schema_and_creation_bound_expansion_rejected(self):
        e=self.create();original=self.path.read_bytes()
        for mutate in (lambda s:s.update(version='v1'),lambda s:s['identity']['profile'].update(max_actions=3),
                       lambda s:s['identity']['science_configuration'].update(rational_digits=512)):
            s=strict_json(original);mutate(s);s['identity_hash']=digest(s['identity']);self.path.write_bytes(encoded(s))
            with self.assertRaises(ValueError):self.reopen()
            self.path.write_bytes(original)
    def object_sources(self,*,target='O002',observation_hash=None,name='object-input'):
        """Authored ownership fixture, never natural-learning evidence."""
        paths=self.sources(name,commands=())
        observation=json.loads(paths['observations'].read_text())[-1]['observation']
        paths['ora'].write_bytes(canonical({'owned_object_selection':{
            'provenance':'authored_ownership_check','command':{'action':'take','target':target},
            'source_observation_hash':digest(observation) if observation_hash is None else observation_hash}}))
        return paths
    def object_create(self,**kwargs):
        paths=self.object_sources(**kwargs)
        return self.create(paths=paths,discovery_count=0,selection_backend=module.object_adapter.BACKEND)
    def test_authored_object_owned_take_restart_and_no_duplicate(self):
        e=self.object_create();d=e.select_next(0);before=e.read()
        self.assertEqual(d['body']['provenance'],'authored_ownership_check')
        self.assertEqual(d['cases'][0]['hypotheses'],[])
        self.assertEqual(d['command'],{'action':'take','target':'O002'})
        a=before['attempts'][0]['id'];calls=STATS['owned_transition_invocations']
        e=self.reopen();o=e.execute(a,1);STATS['durable_outcomes']+=1
        self.assertEqual(STATS['owned_transition_invocations'],calls+1)
        self.assertEqual(o['after_observation']['inventory_ids'],['O002'])
        self.assertIsNone(o['world_snapshot']['entities']['O002']['position'])
        self.assertNotIn('world_snapshot',d['body'])
        self.assertNotIn('history',o['world_snapshot'])
        with patch.object(module,'transition',side_effect=AssertionError('duplicate object actuation')):
            e=self.reopen();self.assertEqual(e.execute(a,2),o)
            b=e.interpret(o['id'],2);self.assertEqual(b['reason'],'authored_ownership_outcome_only')
            self.assertEqual(b['evaluations'],[])
            e=self.reopen();self.assertEqual(e.execute(a,3),o);self.assertEqual(e.interpret(o['id'],3),b)
            self.assertEqual(len(e.read()['outcomes']),1)
            d2=e.select_next(3);self.assertEqual(d2['status'],'policy_null')
            self.assertEqual(d2['body']['reason'],'stale_public_context')
            self.assertEqual(len(e.read()['attempts']),1)
    def test_authored_object_stale_or_unobservable_request_has_no_authority(self):
        for index,kwargs in enumerate(({'observation_hash':'0'*64},{'target':'O001'})):
            self.path=self.research/f'object-{index}.json'
            e=self.object_create(name=f'object-input-{index}',**kwargs)
            before=e.read()['world']
            with patch.object(module,'transition',side_effect=AssertionError('ineligible object actuation')):
                d=e.select_next(0)
                self.assertEqual(d['status'],'policy_null');self.assertIsNone(d['owner_id'])
                self.assertEqual(e.read()['attempts'],[]);self.assertEqual(e.read()['world'],before)
    def test_authored_object_snapshot_and_receipt_tampering_rejected(self):
        e=self.object_create();e.select_next(0);s=e.read()
        e.execute(s['attempts'][0]['id'],1);STATS['durable_outcomes']+=1
        original=self.path.read_bytes()
        mutations=(
            (lambda o:o['world_snapshot']['entities']['M002'].update(_latched=True),'object snapshot'),
            (lambda o:o['receipt'].update(target='O001'),'receipt differs'),
            (lambda o:o['receipt'].update(success=False),'take receipt'),
        )
        for mutate,reason in mutations:
            s=strict_json(original);o=s['outcomes'][0];mutate(o);o['hash']=module._hash(o)
            self.path.write_bytes(encoded(s))
            with patch.object(module,'transition',side_effect=AssertionError('restart replay')):
                with self.assertRaisesRegex(Conflict,reason):self.reopen()
            self.path.write_bytes(original)
    def test_authored_object_default_off_and_stale_ownership_rejected(self):
        paths=self.object_sources()
        with self.assertRaises(Conflict):
            GroundedExecutive.create(self.path,research_dir=self.research,source_paths=paths,
                discovery_count=0,selection_backend=module.object_adapter.BACKEND)
        e=self.create(paths=paths,discovery_count=0,selection_backend=module.object_adapter.BACKEND)
        e.select_next(0);a=e.read()['attempts'][0]['id']
        with patch.object(module,'transition',side_effect=AssertionError('stale object actuation')):
            self.unchanged(e,lambda:e.execute(a,0));self.unchanged(e,lambda:e.execute('foreign',1))
            self.unchanged(e,lambda:e.select_next(1,command={'action':'take','target':'O001'}))
            e.cancel(a,1);self.unchanged(e,lambda:e.execute(a,2))
    def tearDown(self):
        self.assertLessEqual(self.calls,16,'fixture setup bound')

if __name__=='__main__':
    program=unittest.main(exit=False,verbosity=2)
    print('V2_SYNTHETIC_COUNTS '+json.dumps(STATS,sort_keys=True))
    sys.exit(not program.result.wasSuccessful())
