"""The Poisson tail, twice, using nothing but the standard library.

The detection rule asks one statistical question: if this segment ran at the
company attrition rate, how likely is it to have lost this many people or more?
That is the upper tail of a Poisson distribution, and everything else in the rule
is arithmetic.

**Why this is not scipy.** It was, until scipy stopped importing on a machine
where Windows Application Control blocks the DLL behind `scipy.optimize` — which
`scipy.stats` imports whether or not you use it. Rather than fight the policy, the
dependency went away: forty lines of standard library replace a 90 MB package for
a function the project uses once. The repository now needs pandas, openpyxl,
psycopg and pytest, and nothing here will fail on a locked-down laptop.

**Two implementations, on purpose.** Removing scipy removed the independent
authority the DAX was checked against, so the check moved in here. `survival` is
the one the reference rule uses and mirrors the DAX line for line — the same sum
of the same logarithms — and `survival_by_recurrence` computes the identical
quantity by a completely different route: no logarithms, no gamma function, just
the ratio between consecutive terms. Two algorithms that share no arithmetic have
no plausible way to agree on a wrong answer, and `tests/test_reconciliation.py`
requires them to agree to 1e-12 across the whole range the model uses.
"""

from __future__ import annotations

import math

# The largest k the model ever needs is the exit count of its largest segment,
# which is 28. This ceiling is three hundred times that, and it exists only so a
# runaway input fails loudly instead of looping.
MAX_TERMS = 10_000


def survival(observed: int, expected: float) -> float:
    """P(X >= observed) for X ~ Poisson(expected). The one-sided upper tail.

    Summed in logarithms, exactly as `[Attrition p-value]` does in DAX:

        P(X >= x) = 1 - SUM over k = 0..x-1 of EXP( -lambda + k*LN(lambda) - LN(k!) )

    The logarithms are not decoration. Computing lambda**k / k! directly overflows
    a double at k = 171, and every term here stays in range because it is
    exponentiated only once, at the end.
    """
    if expected is None or not math.isfinite(expected) or expected <= 0:
        # No exposure means no expected exits, and a rate over nothing is
        # undefined rather than infinite. The DAX returns BLANK() here.
        return float("nan")
    if observed <= 0:
        return 1.0  # P(X >= 0) is certainty, whatever the rate.
    if observed > MAX_TERMS:
        raise ValueError(f"{observed} exits exceeds the {MAX_TERMS}-term ceiling")

    log_expected = math.log(expected)
    below = math.fsum(
        math.exp(-expected + k * log_expected - math.lgamma(k + 1))
        for k in range(observed)
    )
    # fsum keeps the cumulative sum exact, but the subtraction can still land a
    # hair outside [0, 1] when the tail is vanishingly small. A probability is
    # clamped, not reported as -2e-17.
    return min(max(1.0 - below, 0.0), 1.0)


def survival_by_recurrence(observed: int, expected: float) -> float:
    """The same tail, computed without logarithms. Exists to check `survival`.

    Each term is the previous one times lambda/k, starting from EXP(-lambda).
    That identity is all this needs — no gamma function, no exponential inside
    the loop — so an error in one implementation cannot hide in the other.

    It is the slower and less numerically robust of the two (EXP(-lambda)
    underflows around lambda = 745, well above anything this model produces),
    which is why it is the checker rather than the checked.
    """
    if expected is None or not math.isfinite(expected) or expected <= 0:
        return float("nan")
    if observed <= 0:
        return 1.0
    if observed > MAX_TERMS:
        raise ValueError(f"{observed} exits exceeds the {MAX_TERMS}-term ceiling")

    term = math.exp(-expected)
    terms = [term]
    for k in range(1, observed):
        term *= expected / k
        terms.append(term)
    return min(max(1.0 - math.fsum(terms), 0.0), 1.0)
