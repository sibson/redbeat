#!/usr/bin/env python3
"""Diff two recorded eval runs.

Usage:
    python compare.py <baseline.json> <candidate.json> [--model MODEL]

The point of this script is to stop a comparison from quietly being invalid.
Two records made against different skill commits, or graded against different
expectations, will happily produce a tidy-looking table of deltas that means
nothing -- so those mismatches are reported before any numbers are.
"""

import argparse
import json
import sys
from collections import defaultdict

PROVENANCE = ('skill_commit', 'evals_verified_against')


def load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def index(record, model=None):
    """Map (eval_name, model) -> run, optionally filtered to one model."""
    out = {}
    for run in record.get('runs', []):
        if model and run.get('model') != model:
            continue
        out[(run.get('eval_name'), run.get('model'))] = run
    return out


def rate(run):
    total = run.get('assertions_total') or 0
    return (run.get('assertions_passed', 0) / total) if total else None


def check_provenance(base, cand):
    """Return warnings for anything that makes the comparison unsound."""
    warnings = []
    for field in PROVENANCE:
        b, c = base.get(field), cand.get(field)
        if b != c:
            warnings.append(
                f'{field} differs: baseline {b!r} vs candidate {c!r} -- '
                f'some of the delta below may not be the model'
            )
    for rec, label in ((base, 'baseline'), (cand, 'candidate')):
        efforts = {r.get('effort') for r in rec.get('runs', [])}
        if 'inherited' in efforts and len(efforts) > 1:
            warnings.append(
                f'{label} mixes inherited and explicit effort levels: '
                f'{sorted(e for e in efforts if e)}'
            )
    return warnings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline')
    p.add_argument('candidate')
    p.add_argument('--model', help='restrict to one model id')
    args = p.parse_args()

    base, cand = load(args.baseline), load(args.candidate)

    for w in check_provenance(base, cand):
        print(f'WARNING  {w}')
    print()

    bi, ci = index(base, args.model), index(cand, args.model)
    keys = sorted(set(bi) | set(ci))
    if not keys:
        print('no runs to compare')
        return 1

    by_model = defaultdict(lambda: [0, 0, 0, 0])  # passed, total, tokens_b, tokens_c

    print(f'{"case":<34} {"model":<20} {"base":>7} {"cand":>7} {"delta":>7}  tokens')
    print('-' * 92)
    for name, model in keys:
        b, c = bi.get((name, model)), ci.get((name, model))
        rb, rc = (rate(b) if b else None), (rate(c) if c else None)
        fb = f'{rb:.0%}' if rb is not None else '--'
        fc = f'{rc:.0%}' if rc is not None else '--'
        fd = f'{rc - rb:+.0%}' if (rb is not None and rc is not None) else '--'
        tb = b.get('tokens', 0) if b else 0
        tc = c.get('tokens', 0) if c else 0
        tok = f'{tb:,} -> {tc:,}' if (tb and tc) else f'{tb or tc:,}'
        print(f'{name[:34]:<34} {(model or "?")[:20]:<20} {fb:>7} {fc:>7} {fd:>7}  {tok}')

        agg = by_model[model]
        if c:
            agg[0] += c.get('assertions_passed', 0)
            agg[1] += c.get('assertions_total', 0)
        agg[2] += tb
        agg[3] += tc

        # An outcome flip is the finding; a pass-rate tie can hide one.
        ob = b.get('outcome_reported') if b else None
        oc = c.get('outcome_reported') if c else None
        if ob and oc and ob != oc:
            print(f'{"":<34} outcome changed: {ob} -> {oc}')

    print('-' * 92)
    for model, (passed, total, tb, tc) in sorted(by_model.items(), key=lambda kv: kv[0] or ''):
        pr = f'{passed / total:.0%}' if total else '--'
        print(f'{model or "?":<20} candidate {pr} ({passed}/{total})   tokens {tb:,} -> {tc:,}')

    print('\nPass rate is the weakest signal here -- read outcome_reported and notes too.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
