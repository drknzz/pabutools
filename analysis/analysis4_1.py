from os import listdir
from pathlib import Path

from pabutools.analysis import priceable
from pabutools.election import parse_pabulib, Cardinality_Sat, Cost_Sat
from pabutools.rules import method_of_equal_shares, greedy_utilitarian_welfare

def go_single(instance, profile, allocation, exhaustive):
    sp = priceable(
        instance=instance,
        profile=profile,
        budget_allocation=allocation,
        stable=True,
        exhaustive=exhaustive,
        verbose=True,
    )
    p = sp if sp.validate() else priceable(
        instance=instance,
        profile=profile,
        budget_allocation=allocation,
        stable=False,
        exhaustive=exhaustive,
        verbose=True,
    )
    res = {
        "allocation": str(allocation),
        "priceable": p.validate(),
        "stable-priceable": sp.validate(),
    }
    return res


def go_sat_class(instance, profile, sat_class):
    mes = method_of_equal_shares(instance=instance, profile=profile, sat_class=sat_class)
    mes_add1 = method_of_equal_shares(instance=instance, profile=profile, sat_class=sat_class, voter_budget_increment=1)
    mes_add1u = greedy_utilitarian_welfare(instance, profile, sat_class=sat_class, initial_budget_allocation=mes_add1)
    greedy = greedy_utilitarian_welfare(instance, profile, sat_class=sat_class)

    none = go_single(instance, profile, mes, False)
    add1 = go_single(instance, profile, mes_add1, False)
    add1u = go_single(instance, profile, mes_add1u, True)
    greedy = go_single(instance, profile, greedy, True)

    print("none", none)
    print("add1", add1)
    print("add1u", add1u)
    print("greedy", greedy)


if __name__ == "__main__":
    for file in listdir("approvals/"):
        instance, profile = parse_pabulib(f"approvals/{file}")

        print(f"sp_existance/{Cardinality_Sat.__name__}/{Path(file).stem}")
        go_sat_class(instance, profile, Cardinality_Sat)

        print(f"sp_existance/{Cost_Sat.__name__}/{Path(file).stem}")
        go_sat_class(instance, profile, Cost_Sat)

