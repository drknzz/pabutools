from __future__ import annotations

from collections.abc import Collection
from typing import List


from pabutools.utils import powerset_no_empty

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
) -> bool:
    for group in powerset_no_empty(profile):
        for proj_set in powerset(instance):
            if not is_large_enough(len(group), profile.num_ballots(), total_cost(proj_set), instance.budget_limit):
                continue

            if all(_prefers_a_to_b(proj_set, budget_allocation, ballot, instance, profile, sat_class) for ballot in group):
                return False
    return True


def _prefers_a_to_b(a: Collection[Project], b: Collection[Project], ballot: AbstractBallot, instance: Instance, profile: AbstractApprovalProfile, sat_class: type[SatisfactionMeasure]) -> bool:
    sat = sat_class(instance, profile, ballot)
    return sat.sat(a) > sat.sat(b)


def core_approval(
    instance: Instance,
    profile: AbstractApprovalProfile,
    sat_class: type[SatisfactionMeasure],
) -> List[List[Project]]:
    core = []
    for proj_set in powerset(instance):
        if total_cost(proj_set) > instance.budget_limit:
            continue

        if is_in_core_approval(instance, profile, sat_class, proj_set):
            core.append(proj_set)
    return core
