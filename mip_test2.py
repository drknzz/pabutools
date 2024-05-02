import json
import os
from pathlib import Path

from mip import OptimizationStatus

from pabutools.analysis import priceable, validate_price_system
from pabutools.election import parse_pabulib, Cost_Sat, Cardinality_Sat
from pabutools.rules import method_of_equal_shares, greedy_utilitarian_welfare, completion_by_rule_combination


import time

def timeit(func):
    """
    Decorator for measuring function's running time.
    """
    def measure_time(*args, **kw):
        start_time = time.time()
        result = func(*args, **kw)
        print("Processing time of %s(): %.2f seconds."
              % (func.__qualname__, time.time() - start_time))
        return result

    return measure_time


def test_ilp(instance, profile, stable, exhaustive, allocation=None):
    res = priceable(
        instance,
        profile,
        budget_allocation=allocation,
        stable=stable,
        exhaustive=exhaustive,
    )

    print()
    print(f"--- STATUS: {res.status}")
    print(f"--- TIME: {res.time_elapsed}")
    print(f"--- ALLOCATION: {res.allocation}")
    print(f"--- VOTER BUDGET: {res.voter_budget}")
    # print(f"--- STATUS: {res.payment_functions}")

    if res.validate():
        assert validate_price_system(
            instance,
            profile,
            budget_allocation=res.allocation,
            voter_budget=res.voter_budget,
            payment_functions=res.payment_functions,
            stable=stable,
            exhaustive=exhaustive,
            verbose=True
        )

    print()
    print("OK")
    print()


def test_all(instance, profile, allocation=None):
    test_ilp(instance, profile, stable=True, exhaustive=True, allocation=allocation)
    test_ilp(instance, profile, stable=True, exhaustive=False, allocation=allocation)
    test_ilp(instance, profile, stable=False, exhaustive=True, allocation=allocation)
    test_ilp(instance, profile, stable=False, exhaustive=False, allocation=allocation)


@timeit
def green(instance, profile):
    def priceable_ex(stable, exhaustive):
        result = priceable(
            instance=instance,
            profile=profile,
            stable=stable,
            exhaustive=exhaustive,
            # verbose=True
        )
        if result.status not in [OptimizationStatus.INFEASIBLE, OptimizationStatus.UNBOUNDED]:
            verified = validate_price_system(
                instance,
                profile,
                budget_allocation=result.allocation,
                voter_budget=result.voter_budget,
                payment_functions=result.payment_functions,
                stable=stable,
                exhaustive=exhaustive,
                verbose=True,
            )
            assert verified
        return result

    p_exh = priceable_ex(False, True)
    print(p_exh.allocation)

    p_no_exh = priceable_ex(False, False) if not p_exh.allocation else p_exh
    print(p_no_exh.allocation)

    sp_exh = priceable_ex(True, True)
    print(sp_exh.allocation)

    sp_no_exh = priceable_ex(True, False) if not sp_exh.allocation else sp_exh
    print(sp_no_exh.allocation)


    # print(sp_no_exh.allocation)
    # "non-exhaustive": [int(str(c)) for c in p_no_exh.allocation]
    res = {
        "priceable": {
            "non-exhaustive": str(p_no_exh.allocation),
            "exhaustive____": str(p_exh.allocation)
        },
        "stable-priceable": {
            "non-exhaustive": str(sp_no_exh.allocation),
            "exhaustive____": str(sp_exh.allocation)
        },
    }
    return res

@timeit
def mes(instance, profile):
    def mes_ex(sat_class, voter_budget_increment=None):
        return method_of_equal_shares(
            instance=instance,
            profile=profile,
            sat_class=sat_class,
            voter_budget_increment=voter_budget_increment,
        )

    def mes_greedy_ex(sat_class, voter_budget_increment=None):
        return completion_by_rule_combination(
            instance=instance,
            profile=profile,
            rule_sequence=[method_of_equal_shares, greedy_utilitarian_welfare],
            rule_params=[{"sat_class": sat_class, "voter_budget_increment": voter_budget_increment}, {"sat_class": sat_class}],
        )

    def block(allocation):
        p = priceable(instance, profile, budget_allocation=allocation, exhaustive=False).validate()
        return {
            "allocation": str(allocation),
            "priceable": p,
            "stable-priceable": p and priceable(instance, profile, budget_allocation=allocation, stable=True, exhaustive=False).validate(),
        }

    mes_cost = mes_ex(Cost_Sat)
    print(mes_cost, instance.is_feasible(mes_cost), instance.is_exhaustive(mes_cost))

    mes_cost_u = mes_greedy_ex(Cost_Sat)
    print(mes_cost_u, instance.is_feasible(mes_cost_u), instance.is_exhaustive(mes_cost_u))

    mes_cost_add1 = mes_ex(Cost_Sat, 1)
    print(mes_cost_add1, instance.is_feasible(mes_cost_add1), instance.is_exhaustive(mes_cost_add1))

    mes_cost_add1u = mes_greedy_ex(Cost_Sat, 1)
    print(mes_cost_add1u, instance.is_feasible(mes_cost_add1u), instance.is_exhaustive(mes_cost_add1u))


    mes_cardinal = mes_ex(Cardinality_Sat)
    print(mes_cardinal, instance.is_feasible(mes_cardinal), instance.is_exhaustive(mes_cardinal))

    mes_cardinal_u = mes_greedy_ex(Cardinality_Sat)
    print(mes_cardinal_u, instance.is_feasible(mes_cardinal_u), instance.is_exhaustive(mes_cardinal_u))

    mes_cardinal_add1 = mes_ex(Cardinality_Sat, 1)
    print(mes_cardinal_add1, instance.is_feasible(mes_cardinal_add1), instance.is_exhaustive(mes_cardinal_add1))

    mes_cardinal_add1u = mes_greedy_ex(Cardinality_Sat, 1)
    print(mes_cardinal_add1u, instance.is_feasible(mes_cardinal_add1u), instance.is_exhaustive(mes_cardinal_add1u))

    res = {
        "cost_sat": {
            "none": block(mes_cost),
            "u": block(mes_cost_u),
            "add1": block(mes_cost_add1),
            "add1u": block(mes_cost_add1u),
        },
        "cardinality_sat": {
            "none": block(mes_cardinal),
            "u": block(mes_cardinal_u),
            "add1": block(mes_cardinal_add1),
            "add1u": block(mes_cardinal_add1u),
        },
    }
    return res


@timeit
def greedy(instance, profile):
    def greedy_ex(sat_class):
        return greedy_utilitarian_welfare(
            instance=instance,
            profile=profile,
            sat_class=sat_class,
        )

    def block(allocation):
        p = priceable(instance, profile, budget_allocation=allocation, exhaustive=False).validate()
        return {
            "allocation": str(allocation),
            "priceable": p,
            "stable-priceable": p and priceable(instance, profile, budget_allocation=allocation, stable=True, exhaustive=False).validate(),
        }

    greedy_cost = greedy_ex(Cost_Sat)
    greedy_cardinal = greedy_ex(Cardinality_Sat)

    res = {
        "cost_sat": block(greedy_cost),
        "cardinality_sat": block(greedy_cardinal),
    }
    return res


if __name__ == "__main__":
    # file_path = "analysis/poland_wieliczka_2023.pb"
    # file_path = "tests/PaBuLib/All/poland_gdansk_2020_.pb"
    # file_path = "tests/PaBuLib/All/poland_gdynia_2020_.pb"
    file_path = "tests/PaBuLib/All/poland_katowice_2021_.pb"
    # file_path = "tests/PaBuLib/All/poland_warszawa_2021_.pb"
    # file_path = "tests/PaBuLib/All/poland_lodz_2020_.pb"
    # file_path = "tests/PaBuLib/All/poland_krakow_2018_.pb"
    # file_path = "tests/PaBuLib/All/poland_warszawa_2020_ursus.pb"


    # file_path = "tests/PaBuLib/All/poland_warszawa_2023_wola.pb" # :(
    instance, profile = parse_pabulib(file_path)

    model_cache_path = f"model_cache/{Path(file_path).stem}.lp"
    if os.path.exists(model_cache_path):
        os.remove(model_cache_path)
        print(f"{model_cache_path} removed successfully")
    else:
        print(f"{model_cache_path} does not exist")


    # test_all(instance, profile)


    # mes = method_of_equal_shares(
    #     instance,
    #     profile,
    #     sat_class=Cost_Sat,
    #     voter_budget_increment=1  # use the completion method Add1
    # )
    # print(f"--- EXHAUSTIVE: {instance.is_exhaustive(mes)}")

    # static_mes = {17, 19, 20, 24, 25, 26, 29, 32, 33, 34, 36, 39, 40, 41, 42, 43, 46, 56, 58, 6, 60, 61, 62, 69, 7, 70, 71, 74, 88, 9}
    # mes = [project for project in instance if int(project.name) in static_mes]

    # test_all(instance, profile, mes)



    # greedy = greedy_utilitarian_welfare(
    #     instance,
    #     profile,
    #     sat_class=Cardinality_Sat,
    # )
    # print(f"--- EXHAUSTIVE: {instance.is_exhaustive(greedy)}")
    #
    # test_all(instance, profile, greedy)

    ilp_ = green(instance, profile)
    mes_ = mes(instance, profile)
    greedy_ = greedy(instance, profile)
    res = {
        "ilp": ilp_,
        "mes": mes_,
        "greedy": greedy_,
    }
    print(res)

    with open(f"green/{Path(file_path).stem}.json", "w") as file:
        s = json.dumps(
            res,
            sort_keys=True,
            indent=4
        )
        file.write(s)


