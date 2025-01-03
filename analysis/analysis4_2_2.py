from pathlib import Path
from os import listdir

from pabutools.analysis import priceable
from pabutools.analysis.priceability_relaxation import MinMul, MinAddOffset, MinAddVectorPositive, MinAddVector, MinAdd
from pabutools.election import parse_pabulib, Cardinality_Sat, Cost_Sat
from pabutools.rules import method_of_equal_shares


def go_sat_class(instance, profile, sat_class, relaxation_class):
    mes = method_of_equal_shares(instance=instance, profile=profile, sat_class=sat_class)
    mes_add1 = method_of_equal_shares(instance=instance, profile=profile, sat_class=sat_class, voter_budget_increment=1)

    res_mes = priceable(
        instance=instance,
        profile=profile,
        budget_allocation=mes,
        stable=True,
        exhaustive=False,
        verbose=True,
        relaxation=relaxation_class(instance, profile)
    )

    res_add1 = priceable(
        instance=instance,
        profile=profile,
        budget_allocation=mes_add1,
        stable=True,
        exhaustive=False,
        verbose=True,
        relaxation=relaxation_class(instance, profile)
    )

    return res_mes, res_add1

def go_optimal(instance, profile, relaxation_class):
    if relaxation_class in [MinAddVector, MinAddOffset]:
        res_optimal = priceable(instance, profile, stable=True, exhaustive=False, verbose=True, relaxation=relaxation_class(instance, profile), max_seconds=900)
    else:
        res_optimal = priceable(instance, profile, stable=True, exhaustive=False, verbose=True, relaxation=relaxation_class(instance, profile))

    return res_optimal

def go_file(file_path):
    print(file_path)
    instance, profile = parse_pabulib(file_path)
    for relaxation_class in [MinMul, MinAdd, MinAddVector, MinAddVectorPositive, MinAddOffset]:
        res_card, res_add1_card = go_sat_class(instance, profile, Cardinality_Sat, relaxation_class)
        res_cost, res_add1_cost = go_sat_class(instance, profile, Cost_Sat, relaxation_class)
        res_optimal = go_optimal(instance, profile, relaxation_class)
        print(f"sp_of_mes/{relaxation_class.__name__}/{Path(file_path).stem}")
        s1 = f"{res_card.status}, {res_cost.status}, {res_add1_card.status}, {res_add1_cost.status}, {res_optimal.status}"
        s2 = f"{res_card.allocation}\n{res_cost.allocation}\n{res_add1_card.allocation}\n{res_add1_cost.allocation}\n{res_optimal.allocation}"
        s3 = f"{res_card.relaxation_beta}\n{res_cost.relaxation_beta}\n{res_add1_card.relaxation_beta}\n{res_add1_cost.relaxation_beta}\n{res_optimal.relaxation_beta}"
        print(s1)
        print(s2)
        print(s3)

if __name__ == "__main__":
    for district in listdir("krk_districts/"):
        go_file(f"krk_districts/{district}")