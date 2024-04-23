from __future__ import annotations

import collections
import dataclasses
import json
import time
from collections.abc import Collection
from enum import Enum
from typing import List, Tuple, Dict, Any

from mip import Model, xsum, BINARY, OptimizationStatus, INF, minimize, INT_MAX

from pabutools.analysis.priceability import PriceableResult
from pabutools.election import (
    Instance,
    AbstractApprovalProfile,
    Project,
    total_cost,
)
from pabutools.utils import Numeric, round_cmp

CHECK_ROUND_PRECISION = 2
ROUND_PRECISION = 6
SOLVER_NAME = "gurobi"


def validate_price_system_relax(
    instance: Instance,
    profile: AbstractApprovalProfile,
    budget_allocation: Collection[Project],
    voter_budget: Numeric,
    payment_functions: List[Dict[Project, Numeric]],
    stable: bool = False,
    exhaustive: bool = True,
    relax: Relaxation = 0,
    beta = None,
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
        s = sum(pf[idx][c] for idx, _ in enumerate(N))
        if round_cmp(s, 0, CHECK_ROUND_PRECISION) != 0:
            errors["C4"].append(f"payments for not selected project {c} are equal {s} != 0")

    if not stable:
        for c in NW:
            s = sum(leftover[idx] for idx, i in enumerate(N) if c in i)
            if round_cmp(s, c.cost, CHECK_ROUND_PRECISION) > 0:
                errors["C5"].append(f"voters' leftover money for not selected project {c} are equal {s} > {c.cost}")
    else:
        for c in NW:
            s = sum(max(max_payment[idx], leftover[idx]) for idx, i in enumerate(N) if c in i)

            if relax == Relaxation.NONE:
                cost = c.cost
            elif relax == Relaxation.MIN_MUL:
                cost = c.cost * beta
            elif relax == Relaxation.MIN_ADD:
                cost = c.cost + beta
            elif relax == Relaxation.MIN_ADD_VECTOR or relax == Relaxation.MIN_ADD_VECTOR_POSITIVE:
                cost = c.cost + beta["beta"][c]
            elif relax == Relaxation.MIN_ADD_MIX:
                cost = c.cost + beta["beta_global"] + beta["beta"][c]

            if round_cmp(s, cost, CHECK_ROUND_PRECISION) > 0:
                errors["S5"].append(f"voters' leftover money (or the most they've spent for a project) for not selected project {c} are equal {s} > {cost}")

    if verbose:
        for condition, error in errors.items():
            print(f"({condition}) {error}")

    return not errors


BudgetAllocation = List[Project]


class Relaxation(str, Enum):
    NONE = "NONE"
    MIN_MUL = "MIN_MUL"
    MIN_ADD = "MIN_ADD"
    MIN_ADD_VECTOR = "MIN_ADD_VECTOR"
    MIN_ADD_VECTOR_POSITIVE = "MIN_ADD_VECTOR_POSITIVE"
    MIN_ADD_MIX = "MIN_ADD_MIX"


@dataclasses.dataclass
class RelaxedPriceableResult:
    status: OptimizationStatus
    relaxation: Relaxation
    time: float
    beta: Any = None
    allocation: BudgetAllocation | None = None
    voter_budget: float | None = None
    payment_functions: List[Dict[Project, float]] | None = None
    meta: dict = dataclasses.field(default_factory=dict)

    def validate(self) -> bool:
        return self.status in [OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE]

    def to_dict(self):
        if not self.validate():
            return {"status": str(self.status)}
        res = self.__dict__
        res["status"] = str(self.status)
        res["allocation"] = [str(x) for x in self.allocation]
        # res["payment_functions"] = [{str(k): v for k, v in pf.items() if v > 0} for pf in self.payment_functions]
        del res["payment_functions"]
        if isinstance(self.beta, dict):
            for k, v in self.beta.items():
                if isinstance(v, dict):
                    res["beta"][str(k)] = {str(k_): v_ for k_, v_ in v.items() if v_ != 0}
                else:
                    res["beta"][str(k)] = v
            # res["beta"] = {str(k): v for k, v in self.beta.items() if v != 0}
        return res


def priceable_relax(
    instance: Instance,
    profile: AbstractApprovalProfile,
    budget_allocation: Collection[Project] | None = None,
    voter_budget: Numeric | None = None,
    payment_functions: List[Dict[Project, Numeric]] | None = None,
    stable: bool = False,
    exhaustive: bool = True,
    relax: Relaxation = 0,
) -> RelaxedPriceableResult:
    """Find a priceable budget allocation for approval profile"""
    _start_time = time.time()
    C = instance
    N = profile

    mip_model = Model("stable-priceability" if stable else "priceability", solver_name=SOLVER_NAME)
    # mip_model = Model("stable-priceability" if stable else "priceability", solver_name="cbc")
    # mip_model.verbose = 0

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
            mip_model += cost_total + c.cost + x_vars[c] * instance.budget_limit * 10 >= instance.budget_limit + 1
    elif budget_allocation is None:
        # prevent empty allocation as a result
        mip_model += b * profile.num_ballots() >= instance.budget_limit

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
        mip_model += c.cost + (x_vars[c] - 1) * INT_MAX <= payments_total

    # (C4) voters do not pay for not selected projects
    for idx, _ in enumerate(N):
        for c in C:
            mip_model += 0 <= p_vars[idx][c]
            mip_model += p_vars[idx][c] <= x_vars[c] * INT_MAX

    if relax == Relaxation.NONE:
        beta = None
    elif relax == Relaxation.MIN_MUL:
        beta = mip_model.add_var(name="beta")
    elif relax == Relaxation.MIN_ADD:
        beta = mip_model.add_var(name="beta", lb=-INF)
    elif relax == Relaxation.MIN_ADD_VECTOR:
        beta = {c: mip_model.add_var(name=f"beta_{c.name}", lb=-INF) for c in C}


        # beta[c] is zero for selected
        for c in C:
            mip_model += beta[c] <= (1 - x_vars[c]) * instance.budget_limit
            mip_model += (x_vars[c] - 1) * instance.budget_limit <= beta[c]

        # # beta[c] is zero for unselected
        # for c in C:
        #     mip_model += beta[c] <= (1 - x_vars[c]) * instance.budget_limit * 100
        #     mip_model += (x_vars[c] - 1) * instance.budget_limit * 100 <= beta[c]
    elif relax == Relaxation.MIN_ADD_VECTOR_POSITIVE:
        beta = {c: mip_model.add_var(name=f"beta_{c.name}") for c in C}
    elif relax == Relaxation.MIN_ADD_MIX:
        beta_global = mip_model.add_var(name="beta", lb=-INF)
        beta = {c: mip_model.add_var(name=f"beta_{c.name}") for c in C}
        mip_model += xsum(beta[c] for c in C) <= 0.025 * instance.budget_limit

    if not stable:
        r_vars = [mip_model.add_var(name=f"r_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            mip_model += r_vars[idx] == b - xsum(p_vars[idx][c] for c in C)

        # (C5) supporters of not selected project have no more money than its cost
        for c in C:
            mip_model += xsum(r_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + x_vars[c] * INT_MAX
    else:
        m_vars = [mip_model.add_var(name=f"m_{i.name}") for i in N]
        for idx, _ in enumerate(N):
            for c in C:
                mip_model += m_vars[idx] >= p_vars[idx][c]
            mip_model += m_vars[idx] >= b - xsum(p_vars[idx][c] for c in C)

        # (S5) stability constraint
        for c in C:
            if relax == Relaxation.NONE:
                mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + x_vars[c] * instance.budget_limit
            elif relax == Relaxation.MIN_MUL:
                mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost * beta + x_vars[c] * instance.budget_limit
            elif relax == Relaxation.MIN_ADD:
                mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + beta + x_vars[c] * INT_MAX
            elif relax == Relaxation.MIN_ADD_VECTOR or relax == Relaxation.MIN_ADD_VECTOR_POSITIVE:
                mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + beta[c] + x_vars[c] * INT_MAX
            elif relax == Relaxation.MIN_ADD_MIX:
                mip_model += xsum(m_vars[idx] for idx, i in enumerate(N) if c in i) <= c.cost + beta_global + beta[c] + x_vars[c] * INT_MAX
    # mip_model += b * 10 <= instance.budget_limit
    if relax == Relaxation.MIN_MUL:
        mip_model.objective = minimize(beta)
    elif relax == Relaxation.MIN_ADD:
        mip_model.objective = minimize(beta)
    elif relax == Relaxation.MIN_ADD_VECTOR or relax == Relaxation.MIN_ADD_VECTOR_POSITIVE:
        mip_model.objective = minimize(xsum(beta[c] for c in C))
    elif relax == Relaxation.MIN_ADD_MIX:
        mip_model.objective = minimize(beta_global)

    print("start optimize")
    # print(beta)
    status = mip_model.optimize(max_seconds=600)
    # status = mip_model.optimize()
    print(f"STATUS: {status}")
    _elapsed_time = time.time() - _start_time

    # UNBOUNDED sometimes occurs when it's in fact INFEASIBLE
    if status == OptimizationStatus.INF_OR_UNBD:
        # https://support.gurobi.com/hc/en-us/articles/4402704428177-How-do-I-resolve-the-error-Model-is-infeasible-or-unbounded
        #
        mip_model.solver.set_int_param("DualReductions", 0)
        mip_model.reset()
        mip_model.optimize(max_seconds=600)
        status = OptimizationStatus.INFEASIBLE if mip_model.solver.get_int_attr('status') == 3 else OptimizationStatus.UNBOUNDED
        print(f"ACTUAL STATUS: {status}")

    if status in [OptimizationStatus.INFEASIBLE, OptimizationStatus.UNBOUNDED, OptimizationStatus.INF_OR_UNBD]:
        return RelaxedPriceableResult(status=status, relaxation=relax, time=_elapsed_time)

    assert status in [OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE]
    # if status == OptimizationStatus.UNBOUNDED:
    # print(beta)
    # for c in beta:
    #     print(c, beta[c].lb, beta[c].ub, beta[c])
    # print([beta[c].x for c in C])
    # print(b.x)


    if relax == Relaxation.NONE:
        return_beta = None
    elif relax == Relaxation.MIN_MUL or relax == Relaxation.MIN_ADD:
        return_beta = beta.x
    elif relax == Relaxation.MIN_ADD_VECTOR or relax == Relaxation.MIN_ADD_VECTOR_POSITIVE:
        return_beta = collections.defaultdict(int)
        for c in C:
            if beta[c].x:
                return_beta[c] = beta[c].x
        return_beta = {"beta": return_beta, "sum": sum(return_beta.values())}
    elif relax == Relaxation.MIN_ADD_MIX:
        return_beta = collections.defaultdict(int)
        # return_beta["_global"] = beta_global.x
        for c in C:
            if beta[c].x:
                return_beta[c] = beta[c].x
        return_beta = {"beta": return_beta, "beta_global": beta_global.x, "sum": sum(return_beta.values())}
    payment_functions = [collections.defaultdict(float) for _ in range(len(N))]
    for idx, _ in enumerate(N):
        for c in C:
            if p_vars[idx][c].x > 0:
                payment_functions[idx][c] = p_vars[idx][c].x
    # xd = [collections.defaultdict(int, {c: p_vars[idx][c].x for c in C if p_vars[idx][c].x != 0}) for idx, _ in enumerate(N)]
    # print(xd)
    return RelaxedPriceableResult(
        status=status,
        relaxation=relax,
        time=_elapsed_time,
        allocation=list(sorted([c for c in C if x_vars[c].x >= 0.99])),
        voter_budget=b.x,
        payment_functions=payment_functions,
        beta=return_beta
    )
