from __future__ import annotations

from collections.abc import Collection, Set
from typing import List, Tuple, Dict

import mip
from mip import Model, xsum, BINARY, maximize, OptimizationStatus, minimize

from pabutools.election import (
    Instance,
    AbstractApprovalProfile,
    Project,
    total_cost,
)
from pabutools.utils import Numeric, round_cmp

ROUND_PRECISION = 6


def is_priceable(
    instance: Instance,
    profile: AbstractApprovalProfile,
    committee: Collection[Project],
    candidate_price: Numeric | None = None,
    payment_functions: [Dict[Project, Numeric]] | None = None,
    stable: bool = False,
    *,
    verbose: bool = False,
) -> bool:
    """Checks whether a committee is priceable"""
    if candidate_price is None or payment_functions is None:
        status, candidate_price, payment_functions = find_price_system(instance, profile, committee, candidate_price, payment_functions, stable=stable, verbose=verbose)
        return status == OptimizationStatus.OPTIMAL

    return validate_price_system(instance, profile, committee, candidate_price, payment_functions, stable=stable, verbose=verbose)


def validate_price_system(
    instance: Instance,
    profile: AbstractApprovalProfile,
    committee: Collection[Project],
    candidate_price: Numeric,
    payment_functions: [Dict[Project, Numeric]],
    stable: bool = False,
    *,
    verbose: bool = False
) -> bool:
    """Given a price system, verifies whether a committee is priceable"""
    C = instance
    N = profile
    W = committee
    p = candidate_price
    pf = payment_functions

    for i_idx, i in enumerate(N):
        for c in C:
            if c not in i and pf[i_idx][c] > 0:
                if verbose:
                    print(f"(1) not fulfilled: voter {i_idx} paid {pf[i_idx][c]} for unapproved candidate {c}")
                return False

    for i_idx, i in enumerate(N):
        s = sum(pf[i_idx][c] for c in C)
        if s > 1:
            if verbose:
                print(f"(2) not fulfilled: payments of voter {i_idx} are equal {s}")
            return False

    for c in W:
        s = sum(pf[i_idx][c] for i_idx, i in enumerate(N))
        if round_cmp(s, p, ROUND_PRECISION-2) != 0:
            if verbose:
                print(f"(3) not fulfilled: payments for elected candidate {c} are equal {s}")
            return False

    for c in C:
        if c not in W:
            if (s := sum(pf[i_idx][c] for i_idx, i in enumerate(N))) > 0:
                if verbose:
                    print(f"(4) not fulfilled: payments for unelected candidate {c} are equal {s}")
                return False

    if not stable:
        for c in C:
            if c not in W:
                s = sum(1 - sum(pf[i_idx][c_] for c_ in W) for i_idx, i in enumerate(N) if c in i)
                if round_cmp(s, p, ROUND_PRECISION-2) > 0:
                    if verbose:
                        print(f"(5) not fulfilled: voters' leftover money for unelected candidate {c} are equal {s}")
                    return False
    else:
        for c in C:
            if c not in W:
                s = sum(max(max((pf[i_idx][c_] for c_ in W), default=0), 1 - sum(pf[i_idx][c_] for c_ in W)) for i_idx, i in enumerate(N) if c in i)
                if round_cmp(s, p, ROUND_PRECISION-3) > 0:
                    if verbose:
                        print(f"(5) not fulfilled: voters' leftover money (or the most they've spent for a candidate) for unelected candidate {c} are equal {s}")
                    return False

    return True


Committee = List[Project]


def priceable(
    instance: Instance,
    profile: AbstractApprovalProfile,
    stable: bool = False,
    *,
    resoluteness: bool = True,
    extra_output: bool = False,
) -> Committee | List[Committee] | Tuple[Committee, Numeric, List[Dict[Project, Numeric]]] | List[Tuple[Committee, Numeric, List[Dict[Project, Numeric]]]] | None:
    """Find a priceable committee for approval profile"""
    # TODO: handle return None (no priceable committee)
    C = instance
    N = profile

    mip_model = Model("stable-priceability" if stable else "priceability")
    mip_model.verbose = 0

    # price
    p = mip_model.add_var(name="price")
    mip_model += p <= len(N)

    # payment functions
    p_vars = [{c: mip_model.add_var(name=f"p_{i.name}_{c}") for c in C} for i in N]

    # winning committee [34]
    x_vars = {
        c: mip_model.add_var(var_type=BINARY, name=f"x_{c}")
        for c in C
    }
    # [35]
    mip_model += xsum(x_vars[c] * c.cost for c in C) <= instance.budget_limit

    # (voter can only pay for candidates she approves of)
    for i_idx, i in enumerate(N):
        for c in C:
            if c not in i:
                mip_model += p_vars[i_idx][c] == 0

    # (a voter can pay only for selected committee members) [36]
    for i_idx, i in enumerate(N):
        for c in C:
            mip_model += 0 <= p_vars[i_idx][c]
            mip_model += p_vars[i_idx][c] <= x_vars[c]

    # (a voter will not spend more than its initial budget) [37]
    for i_idx, i in enumerate(N):
        mip_model += xsum(p_vars[i_idx][c] for c in C) <= 1

    # (the sum of the payments for elected candidate equals the price, unelected candidates get payment 0) [38]
    for c in C:
        mip_model += p + (x_vars[c] - 1) * len(N) <= xsum(p_vars[i_idx][c] for i_idx, i in enumerate(N))
        mip_model += xsum(p_vars[i_idx][c] for i_idx, i in enumerate(N)) <= p


    if not stable:
        # (unelected candidates' supporters have no more than p unspent budget)
        r_vars = [mip_model.add_var(name=f"r_{i}") for i in N]
        for i_idx, i in enumerate(N):
            mip_model += r_vars[i_idx] == 1 - xsum(p_vars[i_idx][c] for c in C)

        for c in C:
            mip_model += xsum(r_vars[i_idx] for i_idx, i in enumerate(N) if c in i) <= p + x_vars[c] * len(N)

    else:
        # [39] [40]
        m_vars = [mip_model.add_var(name=f"m_{i}") for i in N]
        for i_idx, i in enumerate(N):
            for c in C:
                mip_model += m_vars[i_idx] >= p_vars[i_idx][c]

            mip_model += m_vars[i_idx] >= 1 - xsum(p_vars[i_idx][c] for c in C)

        # stability constraint [41]
        for c in C:
            mip_model += xsum(m_vars[i_idx] for i_idx, i in enumerate(N) if c in i) <= p + x_vars[c] * len(N)


    # mip_model.objective = maximize(xsum(x_vars[c] * c.cost for c in C))
    # mip_model.objective = maximize(xsum(x_vars[c] for c in C))
    mip_model.objective = minimize(p)   # change down below as well
    # mip_model.emphasis = 2
    status = mip_model.optimize()

    # TODO: handle status other than OPTIMAL; potential lack of solutions
    committee = sorted([c for c in C if x_vars[c].x >= 0.99])

    print(f"xxxSTATUS: {status} | OPT_VAL: {mip_model.objective_value}")

    if resoluteness:
        if extra_output:
            return (
                committee,
                round(p.x, ROUND_PRECISION),
                [{c: round(p_vars[i_idx][c].x, ROUND_PRECISION) for c in C} for i_idx, i in enumerate(N)]
            )
        return committee

    opt_value = mip_model.objective_value

    previous_partial_alloc = committee
    all_partial_allocs = [previous_partial_alloc]
    extra_output_data = [(round(p.x, ROUND_PRECISION), [{c: round(p_vars[i_idx][c].x, ROUND_PRECISION) for c in C} for i_idx, i in enumerate(N)])]

    # mip_model += xsum(x_vars[c] for c in C) == opt_value
    mip_model += p == opt_value
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
            extra_output_data.append((round(p.x, ROUND_PRECISION), [{c: round(p_vars[i_idx][c].x, ROUND_PRECISION) for c in C} for i_idx, i in enumerate(N)]))

    if extra_output:
        return [
            (partial_alloc, price, payment_functions)
            for partial_alloc, (price, payment_functions) in zip(all_partial_allocs, extra_output_data)
        ]
    return all_partial_allocs


def find_price_system(
    instance: Instance,
    profile: AbstractApprovalProfile,
    committee: Set[Project],
    candidate_price: Numeric | None = None,
    payment_functions: [Dict[Project, Numeric]] | None = None,
    stable: bool = False,
    *,
    verbose: bool = False,
) -> bool:
    # TODO: handle return None (no priceable committee)
    C = instance
    N = profile

    if (t := total_cost(committee)) > instance.budget_limit:
        if verbose:
            print(f"Total cost {t} of {committee} exceeded budget limit {instance.budget_limit}")
        return False

    mip_model = Model("stable-priceability" if stable else "priceability")
    mip_model.verbose = 0

    # price
    p = mip_model.add_var(name="price")
    mip_model += p <= len(N)
    if candidate_price is not None:
        mip_model += p == candidate_price

    # payment functions
    p_vars = [{c: mip_model.add_var(name=f"p_{i.name}_{c}") for c in C} for i in N]
    if payment_functions is not None:
        for i_idx, i in enumerate(N):
            for c in C:
                mip_model += p_vars[i_idx][c] == payment_functions[i_idx][c]

    # winning committee [34]
    x_vars = {
        c: int(c in committee)
        for c in C
    }

    # (voter can only pay for candidates she approves of)
    for i_idx, i in enumerate(N):
        for c in C:
            if c not in i:
                mip_model += p_vars[i_idx][c] == 0

    # (a voter can pay only for selected committee members) [36]
    for i_idx, i in enumerate(N):
        for c in C:
            mip_model += 0 <= p_vars[i_idx][c]
            mip_model += p_vars[i_idx][c] <= x_vars[c]

    # (a voter will not spend more than its initial budget) [37]
    for i_idx, i in enumerate(N):
        mip_model += xsum(p_vars[i_idx][c] for c in C) <= 1

    # (the sum of the payments for elected candidate equals the price, unelected candidates get payment 0) [38]
    for c in C:
        mip_model += p + (x_vars[c] - 1) * len(N) <= xsum(p_vars[i_idx][c] for i_idx, i in enumerate(N))
        mip_model += xsum(p_vars[i_idx][c] for i_idx, i in enumerate(N)) <= p


    if not stable:
        # (unelected candidates' supporters have no more than p unspent budget)
        r_vars = [mip_model.add_var(name=f"r_{i}") for i in N]
        for i_idx, i in enumerate(N):
            mip_model += r_vars[i_idx] == 1 - xsum(p_vars[i_idx][c] for c in C)

        for c in C:
            if c not in committee:
                mip_model += xsum(r_vars[i_idx] for i_idx, i in enumerate(N) if c in i) <= p + x_vars[c] * len(N)

    else:
        # [39] [40]
        m_vars = [mip_model.add_var(name=f"m_{i}") for i in N]
        for i_idx, i in enumerate(N):
            for c in C:
                if c in committee:
                    mip_model += m_vars[i_idx] >= p_vars[i_idx][c]

            mip_model += m_vars[i_idx] >= (1 - xsum(p_vars[i_idx][c] for c in C))

        # stability constraint [41]
        for c in C:
            if c not in committee:
                mip_model += xsum(m_vars[i_idx] for i_idx, i in enumerate(N) if c in i) <= p + x_vars[c] * len(N)

    # mip_model.objective = maximize(xsum(x_vars[c] * c.cost for c in C))
    # mip_model.objective = maximize(xsum(x_vars[c] for c in C))
    mip_model.objective = minimize(p)   # change down below as well
    # mip_model.max_seconds = 10
    status = mip_model.optimize()

    # TODO: handle status other than OPTIMAL; potential lack of solutions
    # print(f"STATUS: {status} | OPT_VAL: {mip_model.objective_value}")
    if status == OptimizationStatus.OPTIMAL:
        print(f"p: {p.x}")
        print("payments:")
        for idx, i in enumerate([{c: round(p_vars[i_idx][c].x, ROUND_PRECISION) for c in C} for i_idx, i in enumerate(N)]):
            d = {y: z for y, z in i.items() if z > 0}
            print(f"{idx}: {d}")
        return (
            status,
            round(p.x, ROUND_PRECISION),
            [{c: round(p_vars[i_idx][c].x, ROUND_PRECISION) for c in C} for i_idx, i in enumerate(N)]
        )

    return (status, None, None)
