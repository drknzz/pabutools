from pathlib import Path
from os import listdir

from pabutools.analysis import priceable
from pabutools.analysis.priceability_relaxation import MinMul, MinAddOffset, MinAddVectorPositive, MinAddVector, MinAdd
from pabutools.election import parse_pabulib, Cardinality_Sat, Cost_Sat
from pabutools.rules import method_of_equal_shares, greedy_utilitarian_welfare


def go_sat_class(instance, profile, sat_class, relaxation_class):
    mes_add1 = method_of_equal_shares(instance=instance, profile=profile, sat_class=sat_class, voter_budget_increment=1)
    mes_add1u = greedy_utilitarian_welfare(instance=instance, profile=profile, sat_class=sat_class, initial_budget_allocation=mes_add1)

    greedy = greedy_utilitarian_welfare(instance=instance, profile=profile, sat_class=sat_class)

    res_mes_add1u = priceable(
        instance=instance,
        profile=profile,
        budget_allocation=mes_add1u,
        stable=True,
        exhaustive=True,
        verbose=True,
        relaxation=relaxation_class(instance, profile)
    )

    res_greedy = priceable(
        instance=instance,
        profile=profile,
        budget_allocation=greedy,
        stable=True,
        exhaustive=True,
        verbose=True,
        relaxation=relaxation_class(instance, profile)
    )

    return res_mes_add1u, res_greedy

def go_optimal(instance, profile, relaxation_class):
    if relaxation_class in [MinAddVector, MinAddOffset]:
        res_optimal = priceable(instance, profile, stable=True, exhaustive=True, verbose=True, relaxation=relaxation_class(instance, profile), max_seconds=900)
    else:
        res_optimal = priceable(instance, profile, stable=True, exhaustive=True, verbose=True, relaxation=relaxation_class(instance, profile))

    return res_optimal

def go_file(file_path):
    print(file_path)
    instance, profile = parse_pabulib(file_path)
    for relaxation_class in [MinMul, MinAdd, MinAddVector, MinAddVectorPositive, MinAddOffset]:
        res_mes_card, res_greedy_card = go_sat_class(instance, profile, Cardinality_Sat, relaxation_class)
        res_mes_cost, res_greedy_cost = go_sat_class(instance, profile, Cost_Sat, relaxation_class)
        res_optimal = go_optimal(instance, profile, relaxation_class)
        s1 = f"{res_mes_card.status}, {res_mes_cost.status}, {res_greedy_card.status}, {res_greedy_cost.status}, {res_optimal.status}"
        s2 = f"{res_mes_card.allocation}\n{res_mes_cost.allocation}\n{res_greedy_card.allocation}\n{res_greedy_cost.allocation}\n{res_optimal.allocation}"
        s3 = f"{res_mes_card.relaxation_beta}\n{res_mes_cost.relaxation_beta}\n{res_greedy_card.relaxation_beta}\n{res_greedy_cost.relaxation_beta}\n{res_optimal.relaxation_beta}"
        print(f"mes_vs_greedy/{relaxation_class.__name__}/{Path(file_path).stem}")
        print(s1)
        print(s2)
        print(s3)



if __name__ == "__main__":
    for district in listdir("krk_districts/"):
        go_file(f"krk_districts/{district}")
