from __future__ import annotations

import collections
from collections.abc import Collection
from typing import List, Tuple, Dict

from mip import Model, xsum, BINARY, OptimizationStatus

from pabutools.election import (
    Instance,
    AbstractApprovalProfile,
    Project,
    total_cost,
)
from pabutools.utils import Numeric, round_cmp

CHECK_ROUND_PRECISION = 2
ROUND_PRECISION = 6


def validate_price_system(
    instance: Instance,
    profile: AbstractApprovalProfile,
    budget_allocation: Collection[Project],
    voter_budget: Numeric,
    payment_functions: List[Dict[Project, Numeric]],
    stable: bool = False,
    exhaustive: bool = True,
    *,
    verbose: bool = False
) -> bool:
    """Given a price system, verifies whether budget_allocation is priceable"""
    C = instance
    N = profile
    W = budget_allocation
    NW = [c for c in C if c not in W]
    b = voter_budget
    pf = payment_functions
    total = total_cost(W)
    spent = [sum(pf[idx][c] for c in C) for idx, _ in enumerate(N)]
    leftover = [(b - spent[idx]) for idx, _ in enumerate(N)]
    max_payment = [max((pf[idx][c] for c in C), default=0) for idx, _ in enumerate(N)]

    errors = collections.defaultdict(list)

    # equivalent of `instance.is_feasible(W)`
    if total > instance.budget_limit:
        errors["C0a"].append(f"total price for allocation is equal {total} > {instance.budget_limit}")

    if exhaustive:
        # equivalent of `instance.is_exhaustive(W)`
        for c in NW:
            if total + c.cost <= instance.budget_limit:
                errors["C0b"].append(f"allocation is not exhaustive {total} + {c.cost} = {total + c.cost} <= {instance.budget_limit}")

    # ApprovalBallot inherits from set[Project] so payment_functions must be a list instead of dict (because set cannot be a key as there can be multiple same ballots in the profile)
    for idx, i in enumerate(N):
        for c in C:
            if c not in i and pf[idx][c] != 0:
                errors["C1"].append(f"voter {idx} paid {pf[idx][c]} for unapproved project {c}")

    for idx, _ in enumerate(N):
        if round_cmp(spent[idx], b, CHECK_ROUND_PRECISION) > 0:
            errors["C2"].append(f"payments of voter {idx} are equal {spent[idx]} > {b}")

    for c in W:
        s = sum(pf[idx][c] for idx, _ in enumerate(N))
        if round_cmp(s, c.cost, CHECK_ROUND_PRECISION) != 0:
            errors["C3"].append(f"payments for selected project {c} are equal {s} != {c.cost}")

    for c in NW:
        if (s := sum(pf[idx][c] for idx, _ in enumerate(N))) > 0:
            errors["C4"].append(f"payments for not selected project {c} are equal {s} != 0")

    if not stable:
        for c in NW:
            s = sum(leftover[idx] for idx, i in enumerate(N) if c in i)
            if round_cmp(s, c.cost, CHECK_ROUND_PRECISION) > 0:
                errors["C5"].append(f"voters' leftover money for not selected project {c} are equal {s} > {c.cost}")
    else:
        for c in NW:
            s = sum(max(max_payment[idx], leftover[idx]) for idx, i in enumerate(N) if c in i)
            if round_cmp(s, c.cost, CHECK_ROUND_PRECISION) > 0:
                errors["S5"].append(f"voters' leftover money (or the most they've spent for a project) for not selected project {c} are equal {s} > {c.cost}")

    if verbose:
        for condition, error in errors.items():
            print(f"({condition}) {error}")

    return not errors


BudgetAllocation = List[Project]


def priceable(
    instance: Instance,
    profile: AbstractApprovalProfile,
    budget_allocation: Collection[Project] | None = None,
    voter_budget: Numeric | None = None,
    payment_functions: List[Dict[Project, Numeric]] | None = None,
    stable: bool = False,
    exhaustive: bool = True,
    *,
    extra_output: bool = False,
) -> BudgetAllocation | Tuple[BudgetAllocation, float, List[Dict[Project, float]]] | None:
    """Find a priceable budget allocation for approval profile"""
    C = instance
    N = profile

    mip_model = Model("stable-priceability" if stable else "priceability")
    mip_model.verbose = 0

    # voter budget
    b = mip_model.add_var(name="voter_budget")
    if voter_budget is not None:
        mip_model += b == voter_budget

    # payment functions
    p_vars = [{c: mip_model.add_var(name=f"p_{i.name}_{c.name}") for c in C} for i in N]
    if payment_functions is not None:
        for idx, _ in enumerate(N):
            for c in C:
                mip_model += p_vars[idx][c] == payment_functions[idx][c]

    # winning allocation
    x_vars = {c: mip_model.add_var(var_type=BINARY, name=f"x_{c.name}") for c in C}
    if budget_allocation is not None:
        for c in C:
            if c in budget_allocation:
                mip_model += x_vars[c] == 1
            else:
                mip_model += x_vars[c] == 0

    cost_total = xsum(x_vars[c] * c.cost for c in C)

    # (C0a) the winning allocation is feasible
    mip_model += cost_total <= instance.budget_limit

    if exhaustive:
        # (C0b) the winning allocation is exhaustive
        for c in C:
            mip_model += cost_total + c.cost + x_vars[c] * instance.budget_limit >= instance.budget_limit + 1
    else:
        mip_model += b * instance.num_ballots() >= instance.budget_limit

    # (C1) voter can pay only for projects they approve of
    for idx, i in enumerate(N):
        for c in C:
            if c not in i:
                mip_model += p_vars[idx][c] == 0

    # (C2) voter will not spend more than their initial budget
    for idx, _ in enumerate(N):
        mip_model += xsum(p_vars[idx][c] for c in C) <= b

    # (C3) the sum of the payments for selected project equals its cost
    for c in C:
        payments_total = xsum(p_vars[idx][c] for idx, _ in enumerate(N))

        mip_model += payments_total <= c.cost
        mip_model += c.cost + (x_vars[c] - 1) * instance.budget_limit <= payments_total

    # (C4) voters do not pay for not selected projects
    for idx, _ in enumerate(N):
        for c in C:
            mip_model += 0 <= p_vars[idx][c]
            mip_model += p_vars[idx][c] <= x_vars[c] * instance.budget_limit

    if not stable:
        r_vars = [mip_model.add_var(name=f"r_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            mip_model += r_vars[idx] == b - xsum(p_vars[idx][c] for c in C)

        # (C5) supporters of not selected project have no more money than its cost
        for c in C:
            mip_model += xsum(r_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + x_vars[c] * instance.budget_limit
    else:
        m_vars = [mip_model.add_var(name=f"m_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            for c in C:
                mip_model += m_vars[idx] >= p_vars[idx][c]
            mip_model += m_vars[idx] >= b - xsum(p_vars[idx][c] for c in C)

        # (S5) stability constraint
        for c in C:
            mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + x_vars[c] * instance.budget_limit

    print("start optimize")
    status = mip_model.optimize(max_seconds=300)
    # status = mip_model.optimize()
    print(f"STATUS: {status}")
    if status == OptimizationStatus.INFEASIBLE:
        return None

    budget_allocation = sorted([c for c in C if x_vars[c].x >= 0.99])

    assert status == OptimizationStatus.OPTIMAL

    if extra_output:
        return (
            budget_allocation,
            b.x,
            [{c: p_vars[idx][c].x for c in C} for idx, _ in enumerate(N)]
        )
    return budget_allocation
