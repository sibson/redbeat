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

# USD per million tokens, (input, output). Snapshot -- prices move, and Sonnet 5
# is on introductory pricing, so a record compared long after it was made can be
# costed wrongly. PRICING_AS_OF is printed with every cost figure for that reason.
PRICING_AS_OF = '2026-06-24'
PRICING = {
    'claude-fable-5': (10.00, 50.00),
    'claude-opus-5': (5.00, 25.00),
    'claude-opus-4-8': (5.00, 25.00),
    'claude-opus-4-7': (5.00, 25.00),
    'claude-opus-4-6': (5.00, 25.00),
    'claude-sonnet-5': (2.00, 10.00),  # introductory; reverts to 3.00/15.00 after 2026-08-31
    'claude-sonnet-4-6': (3.00, 15.00),
    'claude-haiku-4-5': (1.00, 5.00),
}

# Runs record total tokens, not the input/output split, so cost needs an assumed
# blend. Agentic loops re-send a large prefix every turn and generate relatively
# little, so they sit well toward input; 0.9 is a deliberate default rather than a
# measurement. Override with --blend and say so if you report the number.
DEFAULT_INPUT_SHARE = 0.9


def cost_usd(model, tokens, input_share):
    """Estimated USD for a run. None when the model isn't in the table."""
    if model not in PRICING or not tokens:
        return None
    price_in, price_out = PRICING[model]
    return tokens * (input_share * price_in + (1 - input_share) * price_out) / 1e6


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
    p.add_argument(
        '--blend',
        type=float,
        default=DEFAULT_INPUT_SHARE,
        help=f'assumed input share of tokens for costing (default {DEFAULT_INPUT_SHARE})',
    )
    args = p.parse_args()

    base, cand = load(args.baseline), load(args.candidate)

    for w in check_provenance(base, cand):
        print(f'WARNING  {w}')

    unpriced = {
        r.get('model')
        for rec in (base, cand)
        for r in rec.get('runs', [])
        if r.get('model') not in PRICING
    }
    if unpriced:
        print(f'WARNING  no price on file for: {", ".join(sorted(m or "?" for m in unpriced))}')
    print()

    bi, ci = index(base, args.model), index(cand, args.model)
    keys = sorted(set(bi) | set(ci))
    if not keys:
        print('no runs to compare')
        return 1

    # passed, total, tokens_b, tokens_c, cost_b, cost_c
    by_model = defaultdict(lambda: [0, 0, 0, 0, 0.0, 0.0])

    header = (
        f'{"case":<32} {"model":<18} {"base":>6} {"cand":>6} '
        f'{"delta":>6}  {"tokens":>17}  {"cost":>15}'
    )
    print(header)
    print('-' * 108)
    for name, model in keys:
        b, c = bi.get((name, model)), ci.get((name, model))
        rb, rc = (rate(b) if b else None), (rate(c) if c else None)
        fb = f'{rb:.0%}' if rb is not None else '--'
        fc = f'{rc:.0%}' if rc is not None else '--'
        fd = f'{rc - rb:+.0%}' if (rb is not None and rc is not None) else '--'
        tb = b.get('tokens', 0) if b else 0
        tc = c.get('tokens', 0) if c else 0
        cb = cost_usd(model, tb, args.blend) or 0.0
        cc = cost_usd(model, tc, args.blend) or 0.0
        tok = f'{tb:,} -> {tc:,}' if (tb and tc) else f'{tb or tc:,}'
        usd = f'${cb:.3f} -> ${cc:.3f}' if (cb and cc) else f'${cb or cc:.3f}'
        print(
            f'{name[:32]:<32} {(model or "?")[:18]:<18} '
            f'{fb:>6} {fc:>6} {fd:>6}  {tok:>17}  {usd:>15}'
        )

        agg = by_model[model]
        if c:
            agg[0] += c.get('assertions_passed', 0)
            agg[1] += c.get('assertions_total', 0)
        agg[2] += tb
        agg[3] += tc
        agg[4] += cb
        agg[5] += cc

        # An outcome flip is the finding; a pass-rate tie can hide one.
        ob = b.get('outcome_reported') if b else None
        oc = c.get('outcome_reported') if c else None
        if ob and oc and ob != oc:
            print(f'{"":<32} outcome changed: {ob} -> {oc}')

    print('-' * 108)
    for model, (passed, total, tb, tc, cb, cc) in sorted(
        by_model.items(), key=lambda kv: kv[0] or ''
    ):
        pr = f'{passed / total:.0%}' if total else '--'
        print(
            f'{model or "?":<18} candidate {pr:>4} ({passed}/{total})   '
            f'tokens {tb:,} -> {tc:,}   cost ${cb:.3f} -> ${cc:.3f}'
        )

    print(
        f'\nCost assumes a {args.blend:.0%}/{1 - args.blend:.0%} input/output token split '
        f'(runs record only totals) at prices as of {PRICING_AS_OF}.'
    )
    print('Pass rate is the weakest signal here -- read outcome_reported and notes too.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
