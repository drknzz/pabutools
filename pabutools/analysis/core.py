from __future__ import annotations

from collections.abc import Collection, Callable, Iterable
from typing import List

from pabutools.utils import powerset_no_empty, Numeric

from pabutools.analysis.cohesiveness import is_large_enough
from pabutools.election import (
    Instance,
    AbstractApprovalProfile,
    Project,
    SatisfactionMeasure,
    total_cost,
    AbstractBallot,
)
from pabutools.utils import powerset


def is_in_core_approval(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    budget_allocation: Collection[Project],
    up_to_func: Callable[[Iterable[Numeric]], Numeric] | None = None,
) -> bool:
    for group in powerset_no_empty(profile):
        for proj_set in powerset(instance):
            if not is_large_enough(len(group), profile.num_ballots(), total_cost(proj_set), instance.budget_limit):
                continue

            if all(_prefers_a_to_b(proj_set, budget_allocation, ballot, instance, profile, sat_class, up_to_func) for ballot in group):
                return False
    return True


def _prefers_a_to_b(
    a: Collection[Project],
    b: Collection[Project],
    ballot: AbstractBallot,
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    up_to_func: Callable[[Iterable[Numeric]], Numeric] | None = None,
) -> bool:
    sat = sat_class(instance, profile, ballot)
    surplus = 0
    if up_to_func is not None:
        surplus = up_to_func(sat.sat_project(p) for p in b if p not in a)
    return sat.sat(a) + surplus > sat.sat(b)


def core_approval(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
    up_to_func: Callable[[Iterable[Numeric]], Numeric] | None = None,
) -> List[List[Project]]:
    core = []
    for proj_set in powerset(instance):
        if total_cost(proj_set) > instance.budget_limit:
            continue

        if is_in_core_approval(instance, profile, sat_class, proj_set, up_to_func):
            core.append(proj_set)
    return core
