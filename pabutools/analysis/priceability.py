from __future__ import annotations

from collections.abc import Collection
from typing import List, Tuple, Dict

from mip import Model, xsum, BINARY, maximize, OptimizationStatus

from pabutools.election import (
    Instance,
    AbstractApprovalProfile,
    Project,
    SatisfactionMeasure,
    AbstractApprovalBallot,
)
from pabutools.utils import Numeric, round_cmp

ROUND_PRECISION = 10


def is_priceable_approval(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    committee: Collection[Project],
    candidate_price: Numeric | None = None,
    payment_functions: Dict[AbstractApprovalBallot, Dict[Project, Numeric]] | None = None,
    *,
    verbose: bool = False,
) -> bool:
    """Checks whether a committee is priceable"""
    # TODO: sat_class
    if candidate_price is None or payment_functions is None:
        if verbose:
            print("candidate_price or payment_functions are None - checking priceability via search")
        return _is_priceable_approval_search(instance, profile, sat_class, committee)

    return _is_priceable_approval_price_system(instance, profile, sat_class, committee, candidate_price, payment_functions, verbose=verbose)


def _is_priceable_approval_search(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    committee: Collection[Project],
) -> bool:
    """Check whether a committee is priceable by matching it with one of generated priceable committees"""
    priceable_committees = priceable_approval(instance, profile, sat_class, resoluteness=False)
    committee = sorted(list(committee))
    # TODO: consider converting priceable_committees to be a generator; potential speed up
    for priceable_committee in priceable_committees:
        if committee == priceable_committee:
            return True
    return False


def _is_priceable_approval_price_system(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    committee: Collection[Project],
    candidate_price: Numeric,
    payment_functions: Dict[AbstractApprovalBallot, Dict[Project, Numeric]],
    *,
    verbose: bool = False
) -> bool:
    """Given a price system, verifies whether a committee is priceable"""
    C = instance
    N = profile
    W = committee
    p = candidate_price
    pf = payment_functions

    for i in N:
        for c in C:
            if c not in i and pf[i][c] > 0:
                # TODO: add logger instead?
                if verbose:
                    print(f"(1) not fulfilled: voter {i} paid {pf[i][c]} for unapproved candidate {c}")
                return False

    for i in N:
        s = sum(pf[i][c] for c in C)
        if s > 1:
            # TODO: add logger instead?
            if verbose:
                print(f"(2) not fulfilled: payments of voter {i} are equal {s}")
            return False

    for c in W:
        s = sum(pf[i][c] for i in N)
        # if round(s, ROUND_PRECISION-2) != round(p, ROUND_PRECISION-2):
        if round_cmp(s, p, ROUND_PRECISION-2) != 0:
            # TODO: add logger instead?
            if verbose:
                print(f"(3) not fulfilled: payments for elected candidate {c} are equal {s}")
            return False

    for c in C:
        if c not in W:
            if (s := sum(pf[i][c] for i in N)) > 0:
                # TODO: add logger instead?
                if verbose:
                    print(f"(4) not fulfilled: payments for unelected candidate {c} are equal {s}")
                return False

    for c in C:
        if c not in W:
            # s1 = sum(pf[i][c_] for c_ in W)
            s = sum(1 - sum(pf[i][c_] for c_ in W) for i in N if c in i)
            # TODO: double round (per sum)?
            # TODO: fraction problem
            # if round(s, ROUND_PRECISION-2) > round(p, ROUND_PRECISION-2):
            if round_cmp(s, p, ROUND_PRECISION-2) == 1:
                # TODO: add logger instead?
                if verbose:
                    print(f"(5) not fulfilled: voters' leftover money for unelected candidate {c} are equal {s}")
                return False

    return True


Committee = List[Project]


def priceable_approval(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    *,
    resoluteness: bool = True,
    extra_output: bool = False,
) -> Committee | List[Committee] | Tuple[Committee, Numeric, Dict] | List[Tuple[Committee, Numeric, Dict]] | None:
    """Find a priceable committee for approval profile"""
    # TODO: handle return None (no priceable committee)
    C = instance
    N = profile

    mip_model = Model("priceability")
    mip_model.verbose = 0

    # price
    p = mip_model.add_var(name="price")
    mip_model += p <= len(N)

    # payment functions
    p_vars = {
        i: {c: mip_model.add_var(name=f"p_{i.name}_{c}") for c in C}
        for i in N
    }

    # winning committee
    x_vars = {
        c: mip_model.add_var(var_type=BINARY, name=f"x_{c}")
        for c in C
    }
    mip_model += xsum(x_vars[c] for c in C) <= instance.budget_limit

    # (1) voter can only pay for candidates she approves of
    for i in N:
        for c in C:
            if c not in i:
                mip_model += p_vars[i][c] == 0

    # (2) (a voter can pay only for selected committee members)
    for i in N:
        for c in C:
            mip_model += 0 <= p_vars[i][c]
            mip_model += p_vars[i][c] <= x_vars[c]

    # (3, 4) (the sum of the payments for elected candidate equals the price, unelected candidates get payment 0)
    for c in C:
        mip_model += p + (x_vars[c] - 1) * len(N) <= xsum(p_vars[i][c] for i in N)  # len(N) -> from (inital money = 1)
        mip_model += xsum(p_vars[i][c] for i in N) <= p

    # (5) (unelected candidates' supporters have no more than p unspent budget)
    r_vars = {i: mip_model.add_var(name=f"r_{i}") for i in N}
    for i in N:
        mip_model += r_vars[i] == 1 - xsum(p_vars[i][c] for c in C)

    for c in C:
        mip_model += xsum(r_vars[i] for i in N if c in i) <= p

    mip_model.objective = maximize(xsum(x_vars[c] for c in C))
    status = mip_model.optimize()

    # TODO: handle status other than OPTIMAL; potential lack of solutions
    committee = sorted([c for c in C if x_vars[c].x >= 0.99])

    if resoluteness:
        if extra_output:
            return (
                committee,
                round(p.x, ROUND_PRECISION),
                {i: {c: round(p_vars[i][c].x, ROUND_PRECISION) for c in C} for i in N}
            )
        return committee

    opt_value = mip_model.objective_value

    previous_partial_alloc = committee
    all_partial_allocs = [previous_partial_alloc]
    extra_output_data = [(round(p.x, ROUND_PRECISION), {i: {c: round(p_vars[i][c].x, ROUND_PRECISION) for c in C} for i in N})]

    mip_model += xsum(x_vars[c] for c in C) == opt_value
    while True:
        # See http://yetanothermathprogrammingconsultant.blogspot.com/2011/10/integer-cuts.html
        # TODO: ref
        mip_model += (
            xsum(1 - x_vars[c] for c in previous_partial_alloc)
            + xsum(x_vars[c] for c in C if c not in previous_partial_alloc)
            >= 1
        )
        mip_model += (
            xsum(x_vars[c] for c in previous_partial_alloc)
            - xsum(x_vars[c] for c in C if c not in previous_partial_alloc)
            <= len(previous_partial_alloc) - 1
        )

        opt_status = mip_model.optimize()
        if opt_status != OptimizationStatus.OPTIMAL:
            break

        previous_partial_alloc = sorted([c for c in C if x_vars[c].x >= 0.99])
        if previous_partial_alloc not in all_partial_allocs:
            all_partial_allocs.append(previous_partial_alloc)
            extra_output_data.append((round(p.x, ROUND_PRECISION), {i: {c: round(p_vars[i][c].x, ROUND_PRECISION) for c in C} for i in N}))

    if extra_output:
        return [
            (partial_alloc, price, payment_functions)
            for partial_alloc, (price, payment_functions) in zip(all_partial_allocs, extra_output_data)
        ]
    return all_partial_allocs
