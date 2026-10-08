"""Default-off, bounded error-driven choice among three observed-action predictors.

No world/simulator, action selection, model API, legacy Phase42 or mutable live
state. The public world topology and candidate predictor families are authored.
Only genuinely prior outcomes change the future model weights.
"""
from __future__ import annotations

from collections import Counter, deque
import argparse
import hashlib
import json
import math
from pathlib import Path

from .action_effect_transfer import (
    BOUNDS, SMOOTHING, StudyInvalid, domain, point, read_evidence, validate_rows,
    SNAPSHOT, JOURNAL,
)

VERSION = 'ora2-adaptive-model-choice-prequential001-v1'
EXPERTS = ('shared_effect', 'exact_context', 'local_exception')
WINDOW, ETA, FLOOR = 64, 0.5, 0.06
WARMUP, EVALUATE, CHUNKS = 1381, 256, 4
TOTAL = WARMUP + EVALUATE
PRIOR_STRENGTH = 2
INITIAL_CHAIN = hashlib.sha256((VERSION + ':observations').encode()).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def proper_distribution(p):
    positions = domain()
    if (set(p) != set(positions) or
            any(type(p[pos]) is not float or not math.isfinite(p[pos]) or not 0 < p[pos] < 1
                for pos in positions) or
            not math.isclose(math.fsum(p[pos] for pos in positions), 1.0,
                             rel_tol=0.0, abs_tol=1e-12)):
        raise StudyInvalid('invalid categorical probability distribution')
    return p


def uniform():
    return {pos: float(1 / len(domain())) for pos in domain()}


def smooth(counts):
    total = sum(counts.values())
    if not total:
        return uniform()
    return proper_distribution({pos: float(SMOOTHING / len(domain()) +
            (1.0 - SMOOTHING) * counts[pos] / total) for pos in domain()})


def weights_from_previous_losses(losses):
    """Only previously observed expert log-losses; 64-case rolling window."""
    if set(losses) != set(EXPERTS) or any(len(losses[name]) > WINDOW for name in EXPERTS):
        raise StudyInvalid('invalid bounded expert history')
    n = len(losses[EXPERTS[0]])
    if any(len(losses[name]) != n for name in EXPERTS):
        raise StudyInvalid('expert update counts differ')
    scores = []
    for name in EXPERTS:
        if any(type(v) is not float or not math.isfinite(v) or v < 0 or v > 16
               for v in losses[name]):
            raise StudyInvalid('invalid saved prospective expert loss')
        scores.append(-ETA * math.fsum(losses[name]))
    peak = max(scores)
    numerators = [math.exp(score - peak) for score in scores]
    denom = math.fsum(numerators)
    return {name: float((1 - FLOOR) * num / denom + FLOOR / len(EXPERTS))
            for name, num in zip(EXPERTS, numerators)}


def metrics(distribution, actual):
    proper_distribution(distribution)
    actual = point(actual)
    probability = distribution[actual]
    loss = -math.log2(probability)
    brier = math.fsum((distribution[pos] - (1.0 if pos == actual else 0.0)) ** 2
                      for pos in domain())
    top = max(sorted(domain()), key=lambda pos: distribution[pos])
    return {'loss_bits': loss, 'brier': brier, 'top_one_correct': top == actual,
            'top_one_probability': distribution[top], 'top_one': list(top),
            'p_actual': probability}


def serialized_probs(distribution):
    return [{'after': list(pos), 'p': distribution[pos]} for pos in domain()]


class AdaptiveModel:
    """One outstanding pre-action forecast, one genuine outcome, exact replay."""

    def __init__(self):
        self.rows = 0
        self.last_cycle = -1
        self.identities = set()
        self.global_effect = {}
        self.local_outcomes = {}
        self.previous_losses = {name: deque(maxlen=WINDOW) for name in EXPERTS}
        self.chain = INITIAL_CHAIN
        self.pending = None

    def preview(self, before, action):
        if self.pending is not None:
            raise StudyInvalid('pending forecast must be completed before another')
        before = point(before)
        if type(action) is not str or not 0 < len(action) <= 128:
            raise StudyInvalid('invalid opaque action')
        observed = Counter()
        for delta, count in self.global_effect.get(action, {}).items():
            destination = tuple(max(-BOUNDS, min(BOUNDS, before[i] + delta[i])) for i in (0, 1))
            observed[destination] += count
        shared = smooth(observed)
        local_counts = self.local_outcomes.get((before, action), Counter())
        exact = smooth(local_counts)
        count = sum(local_counts.values())
        local_weight = count / (count + PRIOR_STRENGTH) if count else 0.0
        hierarchical = proper_distribution({pos: float((1-local_weight) * shared[pos] +
                              local_weight * exact[pos]) for pos in domain()})
        experts = {'shared_effect': shared, 'exact_context': exact,
                   'local_exception': hierarchical}
        weight = weights_from_previous_losses(self.previous_losses)
        adaptive = proper_distribution({pos: float(math.fsum(weight[name] * experts[name][pos]
                  for name in EXPERTS)) for pos in domain()})
        self.pending = {'before': before, 'action': action, 'experts': experts,
                        'weights': weight, 'adaptive': adaptive,
                        'observed_history_length': self.rows,
                        'prior_chain_sha256': self.chain}
        # Public view intentionally has no outcome field; evaluator may only
        # provide the genuine result to observe() after the preview is complete.
        return {'before': list(before), 'action': action,
                'model_weights': dict(weight),
                'distributions': {'adaptive': serialized_probs(adaptive),
                    **{name:serialized_probs(experts[name]) for name in EXPERTS}},
                'history_length': self.rows, 'prior_chain_sha256': self.chain}

    def observe(self, row):
        if self.pending is None:
            raise StudyInvalid('no pre-outcome forecast for this observation')
        # Validation enforces same world, regular before/after, blocked flag,
        # identity, and a true integer cycle. No protected actuator is used.
        normalized = validate_rows([row])[0]
        before, after, action = normalized['before'], normalized['after'], normalized['action']
        if before != self.pending['before'] or action != self.pending['action']:
            raise StudyInvalid('outcome cannot be attributed to this forecast')
        identity = (normalized['source'], normalized['source_id'])
        if identity in self.identities or normalized['cycle'] < self.last_cycle:
            raise StudyInvalid('duplicate/out-of-order real evidence identity')
        if self.rows >= TOTAL:
            raise StudyInvalid('study budget exhausted')
        model_results = {'adaptive': metrics(self.pending['adaptive'], after)}
        model_results.update({name: metrics(self.pending['experts'][name], after)
                              for name in EXPERTS})
        before_receipt = self.pending
        record = {'sequence': self.rows + 1, 'cycle': normalized['cycle'],
                  'source':normalized['source'], 'source_id':normalized['source_id'],
                  'action':action, 'before':list(before), 'after':list(after),
                  'blocked': normalized['blocked'],
                  'prior_chain_sha256':self.chain,
                  'model_weights':dict(before_receipt['weights']),
                  'distributions': {'adaptive':serialized_probs(before_receipt['adaptive']),
                      **{name:serialized_probs(before_receipt['experts'][name]) for name in EXPERTS}},
                  'scores':model_results}
        self.chain = hashlib.sha256((self.chain + '\n' + encode(record)).encode()).hexdigest()
        record['chain_sha256'] = self.chain
        # Expert fitness changes only AFTER recording the actual observed outcome.
        for name in EXPERTS:
            self.previous_losses[name].append(float(model_results[name]['loss_bits']))
        self.local_outcomes.setdefault((before, action), Counter())[after] += 1
        if not normalized['blocked']:
            delta = (after[0]-before[0],after[1]-before[1])
            self.global_effect.setdefault(action, Counter())[delta] += 1
        self.identities.add(identity)
        self.last_cycle = normalized['cycle']
        self.rows += 1
        self.pending = None
        return record


def one_pass(original_rows):
    if len(original_rows) != TOTAL:
        raise StudyInvalid('historical study has wrong fixed input length')
    # Validate entire provenance before scoring; the model itself receives the
    # rows sequentially, never the future rows in an individual preview.
    validate_rows(original_rows)
    predictor = AdaptiveModel()
    evaluated = []
    for i, row in enumerate(original_rows):
        predictor.preview(row['before'], row['action'])
        receipt = predictor.observe(row)
        if i >= WARMUP:
            evaluated.append(receipt)
    if len(evaluated) != EVALUATE or predictor.rows != TOTAL:
        raise StudyInvalid('registered test cases incomplete')
    return predictor, evaluated


def score(evaluated, chain):
    if len(evaluated) != EVALUATE or any(r['sequence'] != WARMUP + i + 1
                                        for i, r in enumerate(evaluated)):
        raise StudyInvalid('invalid saved evaluation sequence')
    names = ('adaptive', *EXPERTS)
    means = {name: math.fsum(r['scores'][name]['loss_bits'] for r in evaluated)/EVALUATE
             for name in names}
    brier = {name: math.fsum(r['scores'][name]['brier'] for r in evaluated)/EVALUATE
             for name in names}
    accuracy = {name: sum(r['scores'][name]['top_one_correct'] for r in evaluated)/EVALUATE
                for name in names}
    best = min(EXPERTS, key=lambda name: (means[name], name))
    blocks = []
    for n in range(CHUNKS):
        records = evaluated[n*(EVALUATE//CHUNKS):(n+1)*(EVALUATE//CHUNKS)]
        advantage = math.fsum(r['scores'][best]['loss_bits'] -
                              r['scores']['adaptive']['loss_bits'] for r in records)/len(records)
        blocks.append({'block':n+1,'n':len(records),'advantage_vs_best_fixed_bits':advantage})
    margin = means[best] - means['adaptive']
    calibration = {}
    for name in names:
        bucket = [[] for _ in range(5)]
        for record in evaluated:
            m = record['scores'][name]
            bucket[min(4, int(m['top_one_probability'] * 5))].append(m)
        calibration[name] = [{'bin':i, 'n':len(group),
          'mean_confidence':(math.fsum(x['top_one_probability'] for x in group)/len(group)
                             if group else None),
          'accuracy':(sum(x['top_one_correct'] for x in group)/len(group)
                             if group else None)} for i,group in enumerate(bucket)]
    return {'version':VERSION, 'status':'VALID_RECORDED_PREQUENTIAL_RESULT',
        'evidence_records':TOTAL, 'warmup_records':WARMUP,
        'evaluation_records':EVALUATE,'window':WINDOW,'eta':ETA,'weight_floor':FLOOR,
        'mean_log_loss_bits':means,'mean_multiclass_brier':brier,
        'top_one_accuracy':accuracy, 'five_bin_calibration':calibration,
        'best_posthoc_fixed_spatial_expert':best,
        'advantage_vs_best_fixed_bits_per_case':margin,
        'four_fixed_blocks':blocks,
        'block_wins':sum(block['advantage_vs_best_fixed_bits'] > 0 for block in blocks),
        'screen_met':bool(margin >= 0.01 and sum(x['advantage_vs_best_fixed_bits'] > 0 for x in blocks) >= 3),
        'final_provenance_chain_sha256':chain,
        'original_live_ora_actions':0,'copied_world_actions':0,'persistent_pilot_enabled':False,
        'limitations':'Retrospective, one deterministic world; all three representations and the adaptation rule are engineer-authored. No useful independent action selection, new world transfer, subjective experience or commitment benefit established.'}


def run(snapshot, journal):
    rows = read_evidence(Path(snapshot),Path(journal))
    model,cases = one_pass(rows)
    # Reconstruct from the same saved historical rows in a new independent
    # object; compare the entire 256-case probability and provenance ledger.
    check_model,check_cases=one_pass(rows)
    if encode(cases)!=encode(check_cases) or model.chain!=check_model.chain:
        raise StudyInvalid('cold reconstruction differs')
    result=score(cases,model.chain)
    result.update(snapshot_sha256=SNAPSHOT,journal_sha256=JOURNAL,
                  result_kind=('NARROW_RETROSPECTIVE_SCREEN_MET' if result['screen_met']
                               else 'VALID_NEGATIVE_ADAPTIVE_MODEL_COMPARISON'),cases=cases,
                  cold_replay_identical=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output
    if output.exists() or output.is_symlink() or any(output.resolve().is_relative_to(
            x.resolve().parent) for x in (args.snapshot,args.journal)):
        raise StudyInvalid('report must be new and outside source directory')
    result=run(args.snapshot,args.journal)
    output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','result_kind','screen_met',
             'best_posthoc_fixed_spatial_expert','advantage_vs_best_fixed_bits_per_case',
             'block_wins','evaluation_records','final_provenance_chain_sha256')},sort_keys=True))


if __name__=='__main__':
    main()
