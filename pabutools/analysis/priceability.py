from __future__ import annotations

from collections.abc import Collection
from typing import List, Tuple, Dict

from mip import Model, xsum, BINARY, maximize, OptimizationStatus

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
    budget_allocation: Collection[Project],
    voter_budget: Numeric | None = None,
    payment_functions: List[Dict[Project, Numeric]] | None = None,
    stable: bool = False,
    *,
    verbose: bool = False,
) -> bool:
    """Checks whether a budget allocation is priceable"""
    if voter_budget is None or payment_functions is None:
        status, voter_budget, payment_functions = find_price_system(instance, profile, budget_allocation, voter_budget, payment_functions, stable=stable)
        if status == OptimizationStatus.OPTIMAL and verbose:
            print(f"--- Voter budget: {voter_budget}")
        return status == OptimizationStatus.OPTIMAL

    return validate_price_system(instance, profile, budget_allocation, voter_budget, payment_functions, stable=stable, verbose=verbose)


def validate_price_system(
    instance: Instance,
    profile: AbstractApprovalProfile,
    budget_allocation: Collection[Project],
    voter_budget: Numeric,
    payment_functions: [Dict[Project, Numeric]],
    stable: bool = False,
    *,
    verbose: bool = False
) -> bool:
    """Given a price system, verifies whether budget_allocation is priceable"""
    C = instance
    N = profile
    W = budget_allocation
    b = voter_budget
    pf = payment_functions

    if (t := total_cost(W)) > instance.budget_limit:
        if verbose:
            print(f"(0) not fulfilled: total price for allocation is equal {t} > {instance.budget_limit}")
        return False

    for idx, i in enumerate(N):
        for c in C:
            if c not in i and pf[idx][c] > 0:
                if verbose:
                    print(f"(1) not fulfilled: voter {idx} paid {pf[idx][c]} for unapproved project {c}")
                return False

    for idx, _ in enumerate(N):
        s = sum(pf[idx][c] for c in C)
        if round_cmp(s, b, ROUND_PRECISION-2) > 0:
            if verbose:
                print(f"(2) not fulfilled: payments of voter {idx} are equal {s} > {b}")
            return False

    for c in W:
        s = sum(pf[idx][c] for idx, _ in enumerate(N))
        if round_cmp(s, c.cost, ROUND_PRECISION-2) != 0:
            if verbose:
                print(f"(3) not fulfilled: payments for selected project {c} are equal {s} != {c.cost}")
            return False

    for c in C:
        if c not in W:
            if (s := sum(pf[idx][c] for idx, _ in enumerate(N))) > 0:
                if verbose:
                    print(f"(4) not fulfilled: payments for not selected project {c} are equal {s}")
                return False

    if not stable:
        for c in C:
            if c not in W:
                s = sum(b - sum(pf[idx][c_] for c_ in W) for idx, i in enumerate(N) if c in i)
                if round_cmp(s, c.cost, ROUND_PRECISION-2) > 0:
                    if verbose:
                        print(f"(5) not fulfilled: voters' leftover money for not selected project {c} are equal {s} > {c.cost}")
                    return False
    else:
        for c in C:
            if c not in W:
                s = sum(max(max((pf[idx][c_] for c_ in W), default=0), b - sum(pf[idx][c_] for c_ in W)) for idx, i in enumerate(N) if c in i)
                if round_cmp(s, c.cost, ROUND_PRECISION-3) > 0:
                    if verbose:
                        print(f"(5) not fulfilled: voters' leftover money (or the most they've spent for a project) for not selected project {c} are equal {s} > {c.cost}")
                    return False

    return True


BudgetAllocation = List[Project]


def priceable(
    instance: Instance,
    profile: AbstractApprovalProfile,
    stable: bool = False,
    *,
    extra_output: bool = False,
) -> BudgetAllocation | List[BudgetAllocation] | Tuple[BudgetAllocation, Numeric, List[Dict[Project, Numeric]]] | List[Tuple[BudgetAllocation, Numeric, List[Dict[Project, Numeric]]]] | None:
    """Find a priceable budget allocation for approval profile"""
    C = instance
    N = profile

    mip_model = Model("stable-priceability" if stable else "priceability", solver_name="cbc")
    mip_model.verbose = 0

    # voter budget
    b = mip_model.add_var(name="budget")

    # payment functions
    p_vars = [{c: mip_model.add_var(name=f"p_{i.name}_{c.name}") for c in C} for i in N]

    # winning allocation
    x_vars = {
        c: mip_model.add_var(var_type=BINARY, name=f"x_{c.name}")
        for c in C
    }

    # (total cost of selected projects shouldn't exceed budget limit)
    mip_model += xsum(x_vars[c] * c.cost for c in C) <= instance.budget_limit

    # (voter can only pay for projects they approve of)
    for idx, i in enumerate(N):
        for c in C:
            if c not in i:
                mip_model += p_vars[idx][c] == 0

    # (a voter can pay only for selected projects)
    for idx, _ in enumerate(N):
        for c in C:
            mip_model += 0 <= p_vars[idx][c]
            mip_model += p_vars[idx][c] <= x_vars[c] * instance.budget_limit
            mip_model += p_vars[idx][c] <= b

    # (a voter will not spend more than its initial budget)
    for idx, _ in enumerate(N):
        mip_model += xsum(p_vars[idx][c] for c in C) <= b

    # (the sum of the payments for selected project equals its cost)
    for c in C:
        mip_model += c.cost + (x_vars[c] - 1) * instance.budget_limit <= xsum(p_vars[idx][c] for idx, _ in enumerate(N))
        mip_model += xsum(p_vars[idx][c] for idx, _ in enumerate(N)) <= c.cost

    if not stable:
        # (supporters of not selected project have no more money than its cost)
        r_vars = [mip_model.add_var(name=f"r_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            mip_model += r_vars[idx] == b - xsum(p_vars[idx][c] for c in C)

        for c in C:
            mip_model += xsum(r_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + x_vars[c] * instance.budget_limit

    else:
        m_vars = [mip_model.add_var(name=f"m_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            for c in C:
                mip_model += m_vars[idx] >= p_vars[idx][c]

            mip_model += m_vars[idx] >= b - xsum(p_vars[idx][c] for c in C)

        # (stability constraint)
        for c in C:
            mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + x_vars[c] * instance.budget_limit

    mip_model.objective = maximize(xsum(x_vars[c] * c.cost for c in C))
    status = mip_model.optimize()

    budget_allocation = sorted([c for c in C if x_vars[c].x >= 0.99])

    print(f"STATUS: {status} | OPT_VAL: {mip_model.objective_value}")
    if extra_output:
        return (
            budget_allocation,
            round(b.x, ROUND_PRECISION),
            [{c: round(p_vars[i_idx][c].x, ROUND_PRECISION) for c in C} for i_idx, i in enumerate(N)]
        )
    return budget_allocation


def find_price_system(
    instance: Instance,
    profile: AbstractApprovalProfile,
    budget_allocation: Collection[Project],
    voter_budget: Numeric | None = None,
    payment_functions: List[Dict[Project, Numeric]] | None = None,
    stable: bool = False,
) -> Tuple[OptimizationStatus, float, List[Dict[Project, float]]] | Tuple[OptimizationStatus, None, None]:
    """Find a price system for approval profile, given budget allocation"""
    C = instance
    N = profile
    W = budget_allocation

    mip_model = Model("stable-priceability" if stable else "priceability", solver_name="cbc")
    mip_model.verbose = 0

    # voter budget
    b = mip_model.add_var(name="budget")
    if voter_budget is not None:
        mip_model += b == voter_budget

    # payment functions
    p_vars = [{c: mip_model.add_var(name=f"p_{i.name}_{c.name}") for c in C} for i in N]
    if payment_functions is not None:
        for idx, _ in enumerate(N):
            for c in C:
                mip_model += p_vars[idx][c] == payment_functions[idx][c]

    # winning allocation
    x_vars = {c: int(c in W) for c in C}

    # (voter can only pay for projects they approve of)
    for idx, i in enumerate(N):
        for c in C:
            if c not in i:
                mip_model += p_vars[idx][c] == 0

    # (a voter can pay only for selected projects)
    for idx, _ in enumerate(N):
        for c in C:
            if c not in W:
                mip_model += p_vars[idx][c] == 0
            else:
                mip_model += p_vars[idx][c] <= b

    # (a voter will not spend more than its initial budget)
    for idx, _ in enumerate(N):
        mip_model += xsum(p_vars[idx][c] for c in C) <= b

    # (the sum of the payments for selected project equals its cost)
    for c in C:
        if c in W:
            mip_model += xsum(p_vars[idx][c] for idx, _ in enumerate(N)) == c.cost

    if not stable:
        r_vars = [mip_model.add_var(name=f"r_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            mip_model += r_vars[idx] == b - xsum(p_vars[idx][c] for c in C)

        # (supporters of not selected project have no more money than its cost)
        for c in C:
            if c not in W:
                mip_model += xsum(r_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost

    else:
        m_vars = [mip_model.add_var(name=f"m_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            for c in C:
                if c in W:
                    mip_model += m_vars[idx] >= p_vars[idx][c]

            mip_model += m_vars[idx] >= (b - xsum(p_vars[idx][c] for c in C))

        # (stability constraint)
        for c in C:
            if c not in W:
                mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost

    mip_model.objective = maximize(xsum(x_vars[c] * c.cost for c in C))
    status = mip_model.optimize()

    if status == OptimizationStatus.OPTIMAL:
        return (
            status,
            round(b.x, ROUND_PRECISION),
            [{c: round(p_vars[idx][c].x, ROUND_PRECISION) for c in C} for idx, _ in enumerate(N)]
        )

    return status, None, None
