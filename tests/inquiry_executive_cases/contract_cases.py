"""Tiny synthetic ownership controls; no natural denominator or learning claim."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
from inquiry_executive import executive as module
from inquiry_executive.contracts import (Capacity, Conflict, COMPLETION_RESERVE,
    INTERPRETATION_RESERVE, RECORD_CAP, T2_GROWTH_BOUND, T3_GROWTH_BOUND,
    canonical, digest, encoded, ensure_capacity, profile, strict_json)
from inquiry_executive.executive import InquiryExecutive, _interpret
from inquiry_executive.synthetic import create_sources

INPUTS = {"planning_lab_requested": True, "provenance": "synthetic_control"}


class ExecutiveContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="research-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = create_sources(self.root / "sources")
        self.research = self.root / "research"
        self.research.mkdir()
        self.path = self.research / "capsule.json"
        self.sources = {k:self.fixture[k] for k in ("ora", "world", "observations")}
        self.protected = {str(p):p.read_bytes() for p in self.sources.values()}

    def create(self, **kwargs):
        return InquiryExecutive.create(self.path, research_dir=self.research,
            source_paths=self.sources, enabled=True, **kwargs)

    def prepare(self, **kwargs):
        e = self.create(**kwargs)
        e.admit(self.fixture["proposal"], 0)
        d = e.select_next(INPUTS, 1)
        self.assertIsNotNone(d["attempt_id"])
        return e, d

    def unchanged(self, call, exception=(ValueError, OSError, TypeError)):
        before = self.path.read_bytes()
        with self.assertRaises(exception):
            call()
        self.assertEqual(before,self.path.read_bytes())
        for path, contents in self.protected.items():
            self.assertEqual(contents,Path(path).read_bytes())

    def reopen(self):
        return InquiryExecutive(self.path,research_dir=self.research,enabled=True)

    def two_inquiries(self):
        self.fixture=create_sources(self.root/'two-sources',case='two_inquiries')
        self.sources={k:self.fixture[k] for k in ('ora','world','observations')}
        self.protected={str(p):p.read_bytes() for p in self.sources.values()}
        e=self.create()
        a=e.admit(self.fixture['proposal'],0)
        b=e.admit(self.fixture['competitor_proposal'],1)
        return e,a,b

    def test_real_missing_feature_outcome_and_later_freshness_deferral(self):
        e,a,b=self.two_inquiries()
        d=e.select_next(INPUTS,2)
        prediction=deepcopy(e.read()['attempts'][0]['contract']['prediction'])
        outcome=e.execute(d['attempt_id'],3)
        self.assertTrue(outcome['receipt']['success'])
        belief=e.recover_or_interpret()
        self.assertEqual(belief['reason'],'missing_evidence')
        self.assertTrue(all(row['verdict']=='unevaluable' for row in belief['evaluations']))
        middle=e.select_next(INPUTS,5)
        self.assertEqual(middle['inquiry_id'],b['id'])
        self.assertIsNone(middle['attempt_id'])
        self.assertEqual(middle['deferral_reason'],'selected_inquiry_without_owned_native_experiment')
        later=e.select_next(INPUTS,6)
        self.assertEqual(later['inquiry_id'],a['id'])
        self.assertIsNone(later['attempt_id'])
        self.assertEqual(later['deferral_reason'],'feature_temporarily_unavailable')
        self.assertEqual(e.read()['attempts'][0]['contract']['prediction'],prediction)
        self.assertEqual(e.read()['counters']['actions'],1)

    def test_prepared_a_b_a_lifecycle_with_explicit_routing_test_double(self):
        # This is only a state-machine control. Real Core B routing is tested
        # separately as a truthful null; this injected return does not establish
        # real B authority or satisfy the real-selector positive control.
        e,a,b=self.two_inquiries()
        first=e.select_next(INPUTS,2)
        real=module.run_cycle
        def state_machine_b(*args,**kwargs):
            bridge=real(*args,**kwargs)
            self.assertEqual(bridge['selection']['question_id'],b['question_id'])
            native=next(x for x in bridge['post_state']['experiments'] if x['id']==b['experiment_id'])
            bridge['result']['experiment']=deepcopy(native)
            bridge['result']['experiment_routing']['returned_experiment_id']=native['id']
            bridge['events'][0]['experiment_id']=native['id']
            bridge['events'][0]['experiment_routing']['returned_experiment_id']=native['id']
            bridge['selection']['experiment_id']=native['id']
            bridge['selection']['experiment']=deepcopy(native)
            bridge['selection']['experiment_routing']['returned_experiment_id']=native['id']
            return bridge
        with patch.object(module,'run_cycle',side_effect=state_machine_b):
            second=e.select_next(INPUTS,3)
        self.assertEqual(second['inquiry_id'],b['id'])
        self.assertIsNotNone(second['attempt_id'])
        self.unchanged(lambda:e.execute(first['attempt_id'],4))
        third=e.select_next(INPUTS,4)
        self.assertEqual(third['inquiry_id'],a['id'])
        self.assertIsNotNone(third['attempt_id'])
        self.assertNotEqual(third['attempt_id'],first['attempt_id'])
        self.unchanged(lambda:e.execute(second['attempt_id'],5))
        self.assertEqual([x['status'] for x in e.read()['attempts']],['cancelled','cancelled','prepared'])
        self.assertEqual(e.read()['counters']['actions'],0)

    def test_json_booleans_cannot_impersonate_revision_or_bounded_integers(self):
        e=self.create();clean=self.path.read_bytes()
        for field,reason in (('revision','capsule revision'),('reserve','completion reserve')):
            state=strict_json(clean);state[field]=False;self.path.write_bytes(encoded(state))
            with self.assertRaisesRegex(ValueError,reason):self.reopen()
        self.path.write_bytes(clean)
        e.admit(self.fixture['proposal'],0);admitted=self.path.read_bytes()
        mutations=[
            (lambda s:s['events'][0].update(revision=True),'event revision'),
            (lambda s:s['frames'][0].update(sequence=True),'frame sequence'),
            (lambda s:s['inquiries'][0]['hypothesis_versions'][0].update(version=True),'hypothesis version'),
        ]
        for mutate,reason in mutations:
            state=strict_json(admitted);mutate(state);self.path.write_bytes(encoded(state))
            bad=self.path.read_bytes()
            with self.assertRaisesRegex(ValueError,reason):self.reopen()
            self.assertEqual(bad,self.path.read_bytes())
        self.path.write_bytes(admitted)
        d=e.select_next(INPUTS,1);prepared=self.path.read_bytes()
        for field in ('hypothesis_version','expected_revision','budget_ordinal'):
            state=strict_json(prepared);state['attempts'][0]['contract'][field]=True
            self.path.write_bytes(encoded(state))
            with self.assertRaisesRegex(ValueError,'attempt '+field.replace('_',' ')):self.reopen()
        self.path.write_bytes(prepared)
        e.execute(d['attempt_id'],2);e.recover_or_interpret()
        state=e.read();state['beliefs'][0]['hypothesis_version']=True
        self.path.write_bytes(encoded(state))
        with self.assertRaisesRegex(ValueError,'belief hypothesis version'):self.reopen()

    def test_integral_metadata_and_receipts_reject_equal_floats_and_booleans(self):
        from inquiry_executive.contracts import integral_metadata,strict_receipt
        for field in ('cycle','revision','sequence','candidate_count','association_count',
                      'retained_count','times_selected','last_selected_cycle','expected_revision',
                      'budget_ordinal','evaluable','confirmations','next_episode_index'):
            for value in (False,True,0.0,1.0):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    integral_metadata({'nested':[ {field:value} ]})
        observations=json.loads(self.sources['observations'].read_text())
        before,after=observations[0]['observation'],observations[1]['observation']
        original=observations[1]['receipt']
        for field in ('before','after'):
            receipt=deepcopy(original);receipt[field]=[float(v) for v in receipt[field]]
            with self.assertRaises(ValueError):strict_receipt(receipt,before,after)
        for value in (True,1.0):
            receipt=deepcopy(original);receipt['cycle']=value
            with self.assertRaises(ValueError):strict_receipt(receipt,before,after)

    def test_completed_core_snapshot_cannot_be_rewritten_before_next_selection(self):
        e,d=self.prepare();e.execute(d['attempt_id'],2);e.recover_or_interpret()
        state=e.read();state['ora']['questions'][-1]['times_selected']+=100
        self.path.write_bytes(encoded(state));bad=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'current Core state differs'):self.reopen()
        self.assertEqual(bad,self.path.read_bytes())

    def test_default_disabled_and_missing_reopen(self):
        with self.assertRaises(ValueError):
            InquiryExecutive.create(self.path,research_dir=self.research,source_paths=self.sources)
        self.assertFalse(self.path.exists())
        with self.assertRaises((ValueError,OSError)):
            InquiryExecutive(self.path,research_dir=self.research,enabled=True)
        self.assertFalse(self.path.exists())

    def test_owned_real_selection_atomic_outcome_and_once_interpretation(self):
        e,d=self.prepare()
        self.assertEqual(d["bridge"]["selection"]["question_id"], self.fixture["question_id"])
        self.assertEqual(d["bridge"]["selection"]["experiment_id"], self.fixture["experiment_id"])
        self.assertEqual(d["bridge"]["treatments"]["repository_observation"],"omitted_by_first_slice")
        state=e.read(); prediction=deepcopy(state["attempts"][0]["contract"]["prediction"])
        self.assertEqual(state["reserve"],COMPLETION_RESERVE)
        o=e.execute(d["attempt_id"],2)
        self.assertTrue(o["receipt"]["blocked"])
        committed=e.read()
        self.assertEqual(committed["reserve"],INTERPRETATION_RESERVE)
        self.assertEqual(committed["counters"]["actions"],1)
        before=self.path.read_bytes()
        self.assertEqual(e.execute(d["attempt_id"],2),o)
        self.assertEqual(self.path.read_bytes(),before)
        self.unchanged(lambda:e.select_next(INPUTS,3))
        self.unchanged(lambda:e.admit(self.fixture["proposal"],3))
        with patch.object(module,"transition",side_effect=AssertionError("recovery cannot act")):
            b=self.reopen().recover_or_interpret()
            after=self.path.read_bytes()
            self.assertEqual(self.reopen().recover_or_interpret(),b)
            self.assertEqual(after,self.path.read_bytes())
        final=e.read()
        self.assertEqual(final["reserve"],0)
        self.assertEqual(final["attempts"][0]["contract"]["prediction"],prediction)
        self.assertEqual(final["counters"]["beliefs"],1)
        self.assertEqual(final["ora"]["metrics"],d["bridge"]["post_state"]["metrics"])
        self.unchanged(lambda:e.recover_or_interpret(interpretation_rule="case-local-v2"))

    def test_stale_revision_unknown_attempt_and_cancelled_authority(self):
        e,d=self.prepare()
        self.unchanged(lambda:e.execute(d["attempt_id"],1))
        self.unchanged(lambda:e.execute("unknown",2))
        d2=e.select_next(INPUTS,2)
        self.assertNotEqual(d["attempt_id"],d2["attempt_id"])
        self.assertEqual(e.read()["attempts"][0]["status"],"cancelled")
        self.unchanged(lambda:e.execute(d["attempt_id"],3))
        self.assertEqual(e.read()["counters"]["actions"],0)

    def test_invalid_proposal_or_override_never_commits(self):
        e=self.create()
        for extra in ("selected", "command", "selector", "source_id"):
            proposal=deepcopy(self.fixture["proposal"]);proposal[extra]=True
            self.unchanged(lambda:e.admit(proposal,0))
        for extra in ("observation", "legacy_question", "action_lab", "cognition_provider", "copy_public_observations"):
            self.unchanged(lambda:e.select_next({**INPUTS,extra:True},0))
        proposal=deepcopy(self.fixture["proposal"])
        proposal["hypotheses"][0]["prediction"]={"kind":"shell","values":["rm"]}
        self.unchanged(lambda:e.admit(proposal,0))
        proposal=deepcopy(self.fixture["proposal"]);proposal["hypotheses"][0]["scope"]="x"*513
        self.unchanged(lambda:e.admit(proposal,0))

    def test_binding_conflicts_and_grounding_substitution(self):
        e=self.create()
        self.unchanged(lambda:e.admit(self.fixture["competitor_proposal"],0))
        e.admit(self.fixture["proposal"],0)
        self.unchanged(lambda:e.admit(self.fixture["proposal"],1))
        proposal=deepcopy(self.fixture["proposal"]);proposal["experiment_id"]="X999999"
        self.unchanged(lambda:e.admit(proposal,1))

    def test_default_limits_and_hard_profile_bounds(self):
        self.assertEqual(profile()["max_bytes"],2*1_048_576)
        self.assertEqual(profile()["max_decisions"],8)
        self.assertEqual(profile()["max_actions"],4)
        for kwargs in ({"max_bytes":16*1_048_576+1},{"max_decisions":17},{"max_actions":9},
                       {"max_decisions":1,"max_actions":2},{"max_bytes":True}):
            with self.assertRaises(ValueError): profile(**kwargs)
        with self.assertRaises(ValueError): profile("preserved_input_smoke",input_hash="a"*64)
        with self.assertRaises(ValueError): profile("preserved_input_smoke",max_bytes=256*1_048_576+1,input_hash="a"*64)

    def test_decision_exhaustion_allows_completion(self):
        e,d=self.prepare(limits=profile(max_decisions=1,max_actions=1))
        self.unchanged(lambda:e.select_next(INPUTS,2),Capacity)
        e.execute(d["attempt_id"],2)
        self.reopen().recover_or_interpret()
        self.unchanged(lambda:self.reopen().select_next(INPUTS,4),Capacity)

    def test_action_exhaustion_rejects_new_work(self):
        e,d=self.prepare(limits=profile(max_actions=1))
        e.execute(d["attempt_id"],2);e.recover_or_interpret()
        self.unchanged(lambda:e.select_next(INPUTS,4),Capacity)
        self.unchanged(lambda:e.admit(self.fixture["proposal"],4),Capacity)
        self.assertEqual(e.read()["counters"]["actions"],1)

    def test_reserve_shortfall_rejects_before_transition(self):
        # A complete admission candidate (not an invalid oversized field) must
        # also be measured before committing any inquiry/counter changes.
        small=self.root/'research-small';small.mkdir()
        small_path=small/'capsule.json'
        small_e=InquiryExecutive.create(small_path,research_dir=small,source_paths=self.sources,enabled=True,limits=profile(max_bytes=34_000))
        before=small_path.read_bytes()
        with self.assertRaises(Capacity):small_e.admit(self.fixture['proposal'],0)
        self.assertEqual(before,small_path.read_bytes())
        e=self.create(limits=profile(max_bytes=COMPLETION_RESERVE))
        e.admit(self.fixture["proposal"],0)
        with patch.object(module,"transition",side_effect=AssertionError("no preview")):
            self.unchanged(lambda:e.select_next(INPUTS,1),Capacity)
        self.assertEqual(e.read()["counters"]["decisions"],0)

    def test_exact_capacity_bytes_and_protected_remaining_reserve(self):
        e,d=self.prepare();state=e.read()
        # The pure pre-write size checker includes identity, seal and newline.
        for reserve in (COMPLETION_RESERVE,INTERPRETATION_RESERVE,0):
            candidate=deepcopy(state);candidate["reserve"]=reserve
            # Cap self-description can change digit count, so compute fixed point.
            cap=len(encoded(candidate))+reserve
            for _ in range(3):
                candidate["identity"]["profile"]["max_bytes"]=cap
                candidate["identity_hash"]=digest(candidate["identity"])
                cap=len(encoded(candidate))+reserve
            candidate["identity"]["profile"]["max_bytes"]=cap
            candidate["identity_hash"]=digest(candidate["identity"])
            self.assertEqual(ensure_capacity(candidate),cap-reserve)
            one_over=deepcopy(candidate)
            one_over["identity"]["profile"]["max_bytes"]=cap-1
            one_over["identity_hash"]=digest(one_over["identity"])
            self.assertEqual(len(encoded(one_over))+reserve,cap)
            with self.assertRaises(Capacity):ensure_capacity(one_over)
            candidate["ora"]["capacity_test_growth"]="x"
            with self.assertRaises(Capacity):ensure_capacity(candidate)
        self.assertLess(T2_GROWTH_BOUND+INTERPRETATION_RESERVE,COMPLETION_RESERVE)
        self.assertLess(T3_GROWTH_BOUND,INTERPRETATION_RESERVE)

    def test_serialized_worst_case_completion_envelopes_fit_reserve(self):
        # Conservative algebra deliberately maximizes independently capped
        # components even though fixed Challenge outputs cannot reach all these
        # maxima together. These are size-envelope records, not valid evidence
        # or a claimed naturally reachable result.
        from inquiry_executive.contracts import bounded
        def maximum_json_record(cap):
            row={"payload":""}
            row["payload"]="x"*(cap-len(canonical(row)))
            self.assertEqual(len(canonical(row)),cap)
            bounded(row,cap)
            with self.assertRaises(Capacity):bounded({"payload":row["payload"]+"x"},cap)
            return row
        e,d=self.prepare();before=e.read()
        worst=deepcopy(before)
        # Full outcome charged at 3 records plus metadata, new frame, both
        # recorder copies, one extra world receipt and 8 KiB world changes.
        worst['outcomes'].append(maximum_json_record(3*RECORD_CAP+16_384))
        worst['frames'].append(maximum_json_record(RECORD_CAP))
        worst['recorder']=maximum_json_record(131_072)
        worst['ora']['challenge_shadow_recorder_v1']=maximum_json_record(131_072)
        worst['world']['history'].append(maximum_json_record(RECORD_CAP))
        worst['world']['bounded_structure_growth']=maximum_json_record(8_192-100)
        worst['bounded_attempt_event_growth']=maximum_json_record(16_384-100)
        t2_growth=len(encoded(worst))-len(encoded(before))
        self.assertLessEqual(t2_growth,T2_GROWTH_BOUND)
        interpreted=deepcopy(worst)
        interpreted['beliefs'].append(maximum_json_record(RECORD_CAP))
        interpreted['bounded_belief_metadata_growth']=maximum_json_record(16_384-100)
        t3_growth=len(encoded(interpreted))-len(encoded(worst))
        self.assertLessEqual(t3_growth,T3_GROWTH_BOUND)
        self.assertLess(t2_growth+INTERPRETATION_RESERVE,COMPLETION_RESERVE)
        self.assertLess(t2_growth+t3_growth,COMPLETION_RESERVE)

    def test_oversized_outcome_cannot_mutate_world_or_authority(self):
        e,d=self.prepare();real=module.transition
        def oversized(*args,**kwargs):
            world,receipt=real(*args,**kwargs)
            receipt["observed_effects"].append("x"*RECORD_CAP)
            world["history"][-1]=deepcopy(receipt)
            return world,receipt
        with patch.object(module,"transition",side_effect=oversized):
            self.unchanged(lambda:e.execute(d["attempt_id"],2),ValueError)
        self.assertEqual(e.read()["counters"]["actions"],0)

    def test_tampered_authority_fields_reject_unchanged_even_resealed(self):
        e,d=self.prepare();clean=self.path.read_bytes()
        mutations=[
            lambda s:s["identity"]["adapter"].update(actor="other"),
            lambda s:s["identity"]["profile"].update(max_actions=8),
            lambda s:s["identity"].update(run_id="other"),
            lambda s:s["identity"].update(path="/tmp/other"),
            lambda s:s["identity"]["code_manifest"].update(fake="0"*64),
            lambda s:s["counters"].update(actions=1),
            lambda s:s.update(revision=s["revision"]+1),
            lambda s:s.update(reserve=0),
            lambda s:s["world"].update(position=[2,2]),
            lambda s:s["recorder"].update(chain="0"*64),
            lambda s:s["inquiries"][0].update(status="suspended"),
            lambda s:s["inquiries"][0]["hypothesis_versions"][0]["hypotheses"][0].update(explanation="changed"),
            lambda s:s["inquiries"][0].update(current_belief="unknown"),
            lambda s:s["attempts"][0]["contract"].update(command={"action":"north"}),
            lambda s:s["attempts"][0]["contract"]["prediction"].update(before_value=[2,2]),
            lambda s:s["decisions"][0]["bridge"]["selection"].update(question_id="wrong"),
            lambda s:s["decisions"][0]["bridge"]["selection"].update(thread_id="wrong"),
            lambda s:s["frames"][-1].update(source_id="other"),
            lambda s:s["frames"][-1].update(predecessor="0"*64),
            lambda s:s["frames"].pop(),
            lambda s:s["inquiries"].append(deepcopy(s["inquiries"][0])),
            lambda s:s.update(unknown=True),
            lambda s:s.update(version="unsupported"),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                state=strict_json(clean);mutate(state);self.path.write_bytes(encoded(state))
                bad=self.path.read_bytes()
                with self.assertRaises((ValueError,KeyError,IndexError)):
                    self.reopen().execute(d["attempt_id"],2)
                self.assertEqual(bad,self.path.read_bytes())
        self.path.write_bytes(clean)

    def test_duplicate_keys_nonfinite_and_missing_authority_reject(self):
        e,d=self.prepare();clean=self.path.read_bytes()
        for payload in (b'{"version":1,"version":2}',b'{"x":NaN}',b'{',b'{}'):
            self.path.write_bytes(payload)
            with self.assertRaises(ValueError):self.reopen()
            self.assertEqual(payload,self.path.read_bytes())
        self.path.write_bytes(clean)

    def test_path_alias_symlink_hardlink_relocation_and_missing_file(self):
        e=self.create();original=self.path.read_bytes()
        link=self.research/'alias.json';link.symlink_to(self.path)
        with self.assertRaises((ValueError,OSError)):InquiryExecutive(link,research_dir=self.research,enabled=True)
        os.link(self.path,self.research/'hard.json')
        self.unchanged(lambda:e.read())
        (self.research/'hard.json').unlink()
        moved=self.research/'moved.json';moved.write_bytes(original)
        with self.assertRaises((ValueError,OSError)):InquiryExecutive(moved,research_dir=self.research,enabled=True)
        self.path.unlink()
        with self.assertRaises((ValueError,OSError)):e.read()
        self.assertFalse(self.path.exists())

    def test_source_mutation_and_hardlink_fail_closed(self):
        e,d=self.prepare();source=self.sources['world'];original=source.read_bytes()
        source.write_bytes(original+b' ')
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):e.execute(d['attempt_id'],2)
        self.assertEqual(before,self.path.read_bytes());source.write_bytes(original)
        os.link(source,self.root/'source-alias')
        self.unchanged(lambda:e.execute(d['attempt_id'],2))

    def test_declarative_missing_contradictory_nondiscriminating_outcomes(self):
        e,d=self.prepare();state=e.read();attempt=state['attempts'][0]
        outcome={}
        frame=deepcopy(state['frames'][-1])
        predictions=attempt['contract']['prediction']
        results,reason=_interpret(attempt,outcome,frame)
        self.assertEqual([r['verdict'] for r in results],['supports_this_case','contradicts_this_case'])
        copied=deepcopy(attempt);copied['contract']['prediction']['feature']='entity.absent.state'
        results,reason=_interpret(copied,outcome,frame)
        self.assertEqual(reason,'missing_evidence')
        self.assertTrue(all(r['verdict']=='unevaluable' for r in results))
        copied=deepcopy(attempt)
        copied['contract']['prediction']['hypotheses'][1]['prediction']={'kind':'equal','values':[]}
        results,reason=_interpret(copied,outcome,frame)
        self.assertEqual(reason,'alternatives_undiscriminated')
        self.assertTrue(all(r['verdict']=='supports_this_case' for r in results))

    def test_outcome_transplant_and_duplicate_interpretation_rejected(self):
        e,d=self.prepare();e.execute(d['attempt_id'],2);e.recover_or_interpret()
        d2=e.select_next(INPUTS,4);e.execute(d2['attempt_id'],5);e.recover_or_interpret()
        clean=self.path.read_bytes()
        for mutate in (
            lambda s:s['inquiries'][0].update(current_belief=s['beliefs'][0]['id']),
            lambda s:s['outcomes'][0].update(attempt_id=s['outcomes'][1]['attempt_id']),
            lambda s:s['beliefs'].append(deepcopy(s['beliefs'][0])),
            lambda s:s['beliefs'][0].update(rule='changed'),
            lambda s:s['outcomes'][0].update(after_frame_id=s['outcomes'][1]['after_frame_id']),
        ):
            state=strict_json(clean);mutate(state);self.path.write_bytes(encoded(state));bad=self.path.read_bytes()
            with self.assertRaises(ValueError):self.reopen()
            self.assertEqual(bad,self.path.read_bytes())
        self.path.write_bytes(clean)


class NullSelectionTests(unittest.TestCase):
    def test_real_nulls_count_and_never_substitute_runner_up(self):
        for case in ('unmapped','no_decision'):
            with self.subTest(case=case),tempfile.TemporaryDirectory(prefix='research-null-') as tmp:
                root=Path(tmp);f=create_sources(root/'sources',case=case);research=root/'research';research.mkdir()
                e=InquiryExecutive.create(research/'capsule.json',research_dir=research,source_paths={k:f[k] for k in ('ora','world','observations')},enabled=True,limits=profile(max_decisions=1,max_actions=1))
                revision=0
                if f['proposal']:
                    e.admit(f['proposal'],0);revision=1
                with patch.object(module,'transition',side_effect=AssertionError('null cannot transition')):
                    d=e.select_next(INPUTS,revision)
                self.assertIsNone(d['attempt_id']);self.assertIsNone(d['inquiry_id'])
                self.assertEqual(e.read()['counters']['decisions'],1)
                self.assertEqual(e.read()['counters']['actions'],0)
                before=(research/'capsule.json').read_bytes()
                with self.assertRaises(Capacity):e.select_next(INPUTS,revision+1)
                self.assertEqual(before,(research/'capsule.json').read_bytes())


if __name__ == "__main__":
    unittest.main()
