import json
import os.path
import time
import pickle

from analysis.rules import mes_cost_res, mes_cost_res_ex, seqphragmen_res, maxwelfare_cost_res
from pabutools.analysis.priceability import priceable, validate_price_system
from pabutools.analysis.relaxation import Relaxation, priceable_relax, validate_price_system_relax, \
    RelaxedPriceableResult
from pabutools.election import parse_pabulib, total_cost, Cost_Sat
from pabutools.fractions import frac
from pabutools.rules import method_of_equal_shares, exhaustion_by_budget_increase, greedy_utilitarian_welfare
from mip import OptimizationStatus

STABLE = True
# STABLE = False

# testy z przykladami nie obvious, w ktorych budget na chlopka nie jest po prostu instance_budget / n

def go(instance, profile):
    start = time.time()
    res = priceable(
        instance,
        profile,
        stable=STABLE,
    )
    if res is None:
        print("\nfail\n")
        return
    # budget_allocation, voter_budget, payment_functions = res

    # print()
    # for idx, pf in enumerate(payment_functions):
    #     d = {c: z for c, z in pf.items() if z > 0}
    #     if d:
    #         print(f"{idx}: {d}")
    print()
    print(f"--- TIME: {time.time() - start}")
    print(f"--- Allocation: {res.allocation}")
    print(f"--- Voter budget: {res.voter_budget}")
    print(f"--- COST: {total_cost(res.allocation)}")
    print()

    verified = validate_price_system(
        instance,
        profile,
        budget_allocation=res.allocation,
        voter_budget=res.voter_budget,
        payment_functions=res.payment_functions,
        stable=STABLE,
        verbose=True
    )
    print(f"--- Verified: {verified}")
    print()
    return res

def go_relax(instance, profile, relax, budget_allocation = None):
    start = time.time()
    res = priceable_relax(
        instance,
        profile,
        budget_allocation=budget_allocation,
        stable=STABLE,
        relax=relax
    )
    if res is None:
        print("\nfail\n")
        return

    # print()
    # for idx, pf in enumerate(payment_functions):
    #     d = {c: z for c, z in pf.items() if z > 0}
    #     if d:
    #         print(f"{idx}: {d}")
    print()
    print(f"--- TIME: {res.time}")
    print(f"--- Allocation: {res.allocation}")
    print(f"--- Voter budget: {res.voter_budget}")
    print(f"--- COST: {total_cost(res.allocation)}")
    print(f"--- BETA: {res.beta}")
    # if isinstance(beta, dict):
    #     print(sum(beta.values()))
    # print()

    verified = validate_price_system_relax(
        instance,
        profile,
        budget_allocation=res.allocation,
        voter_budget=res.voter_budget,
        payment_functions=res.payment_functions,
        stable=STABLE,
        relax=relax,
        beta=res.beta,
        verbose=True
    )
    print(f"--- Verified: {verified}")
    print()

    return res



def main():
    RELAXATION = Relaxation.MIN_ADD_MIX

    # instance, profile = parse_pabulib("analysis/poland_wieliczka_2023.pb")
    instance, profile = parse_pabulib("tests/PaBuLib/All/poland_wroclaw_2018_.pb")
    go_relax(instance, profile, RELAXATION)

    # instance, profile = parse_pabulib("analysis/poland_wieliczka_2023.pb", sample_size=1000)
    # go(instance, profile)

    # instance, profile = parse_pabulib("tests/PaBuLiB/All/poland_lodz_2022_teofilow-wielkopolska.pb", sample_size=5000)
    # go(instance, profile)

    static_mes = {17, 19, 20, 24, 25, 26, 29, 32, 33, 34, 36, 39, 40, 41, 42, 43, 46, 56, 58, 6, 60, 61, 62, 69, 7, 70, 71, 74, 88, 9}
    mes = [project for project in instance if int(project.name) in static_mes]
    go_relax(instance, profile, RELAXATION, mes)

    # start4 = time.time()
    # mes_computed = method_of_equal_shares(
    #     instance,
    #     profile,
    #     sat_class=Cost_Sat,
    #     voter_budget_increment=1  # use the completion method Add1
    # )

    # res_computed = maxwelfare_cost_res(instance, profile)
    # print(list(sorted(res_computed)))
    # print(len(res_computed))
    # print(total_cost(res_computed))
    # go_relax(instance, profile, Relaxation.MIN_MUL, res_computed)

    # print(list(sorted(mes)))
    # print(list(sorted(mes_computed)))
    # print(len(mes), len(mes_computed))
    # assert set(mes_computed) == set(mes)


    static_greedy = {24, 41, 40, 74, 19, 6, 21, 32, 39, 58, 42, 25, 16, 43, 20, 60, 29, 33, 17, 70, 34, 87, 8}
    greedy = [project for project in instance if int(project.name) in static_greedy]
    go_relax(instance, profile, RELAXATION, greedy)

    # greedy_computed = greedy_utilitarian_welfare(
    #     instance,
    #     profile,
    #     sat_class=Cost_Sat,
    # )
    # print(list(sorted(greedy)))
    # print(list(sorted(greedy_computed)))
    # print(total_cost(greedy_computed))
    #
    # assert set(greedy_computed) == set(greedy)

    # print()
    # # print(f"--- TIME: {time.time() - start4}")
    # print(f"--- MES: {mes}")
    # print(f"--- MES DIFF: -{[x for x in mes if x not in greedy]} +{[x for x in greedy if x not in mes]}")


def main2():
    instance, profile = parse_pabulib("analysis/poland_wieliczka_2023.pb")
    relax = Relaxation.MIN_MUL
    res = priceable_relax(
        instance,
        profile,
        stable=STABLE,
        relax=relax
    )

    print()
    print(f"--- TIME: {res.time}")
    print(f"--- Allocation: {res.allocation}")
    print(f"--- Voter budget: {res.voter_budget}")
    print(f"--- COST: {total_cost(res.allocation)}")
    print(f"--- BETA: {res.beta}")
    if isinstance(res.beta, dict):
        print(sum(res.beta.values()))
    print()

    # with open("wieliczka.pickle", "wb") as file:
    #     pickle.dump(res, file)

    verified = validate_price_system_relax(
        instance,
        profile,
        budget_allocation=res.allocation,
        voter_budget=res.voter_budget,
        payment_functions=res.payment_functions,
        stable=STABLE,
        relax=relax,
        beta=res.beta,
        verbose=True
    )
    print(f"--- Verified: {verified}")
    print()


def get_all_relax(instance, profile, allocation = None, exhaustive = True):
    RESULT = {}
    for relax in Relaxation:
        print(relax)
        # if relax == Relaxation.MIN_ADD or relax == Relaxation.MIN_ADD_VECTOR or relax == Relaxation.MIN_ADD_MIX:
        if relax != Relaxation.MIN_ADD_VECTOR:
            continue
        res = priceable_relax(
            instance,
            profile,
            stable=STABLE,
            relax=relax,
            budget_allocation=allocation,
            exhaustive=exhaustive,
        )
        if res.status not in [OptimizationStatus.INFEASIBLE, OptimizationStatus.UNBOUNDED]:
            verified = validate_price_system_relax(
                instance,
                profile,
                budget_allocation=res.allocation,
                voter_budget=res.voter_budget,
                payment_functions=res.payment_functions,
                stable=STABLE,
                relax=relax,
                beta=res.beta,
                verbose=True,
                exhaustive=exhaustive
            )
            assert verified

        # res.meta["stable"] = STABLE
        # res.meta["file"] = file_path
        # res.meta["sample_size"] = sample_size
        RESULT[relax] = res.to_dict()

        # if relax == Relaxation.MIN_MUL:
        #     break
    return RESULT

from pathlib import Path

def main_main(file_path):
    # main()
    # main2()

    # file_path = "analysis/poland_wieliczka_2023.pb"
    # file_path = "approval_data/poland_gdansk_2020_.pb"
    # file_path = "approval_data/poland_gdynia_2020_.pb"
    # file_path = "approval_data/poland_lodz_2020_.pb"
    # file_path = "approval_data/poland_lodz_2022_stary-widzew.pb"
    sample_size = None
    instance, profile = parse_pabulib(file_path, sample_size=sample_size)

    RESULT_ALL = {}

    # static_mes = {17, 19, 20, 24, 25, 26, 29, 32, 33, 34, 36, 39, 40, 41, 42, 43, 46, 56, 58, 6, 60, 61, 62, 69, 7, 70, 71, 74, 88, 9}
    # mes = [project for project in instance if int(project.name) in static_mes]
    mes_computed = method_of_equal_shares(
        instance,
        profile,
        sat_class=Cost_Sat,
        voter_budget_increment=1  # use the completion method Add1
        # voter_budget_increment=len(profile),
    )
    # static_mes = {1, 18, 27, 26, 2, 20, 13, 24, 28, 15, 22, 25, 16, 19}
    # mes_computed = [project for project in instance if int(project.name) in static_mes]

    # mes_computed = mes
    print(mes_computed)
    print(len(mes_computed))
    # assert set(mes_computed) == set(mes)
    # print(set(mes_computed) == set(mes))

    # print("start_mes")
    # mes = exhaustion_by_budget_increase(
    #     instance,
    #     profile,
    #     method_of_equal_shares,
    #     {"sat_class": Cost_Sat},
    #     # budget_step=1,
    # )
    # print(mes)
    print(instance.is_feasible(mes_computed))
    print(instance.is_exhaustive(mes_computed))

    # static_greedy = {24, 41, 40, 74, 19, 6, 21, 32, 39, 58, 42, 25, 16, 43, 20, 60, 29, 33, 17, 70, 34, 87, 8}
    # greedy = [project for project in instance if int(project.name) in static_greedy]
    greedy = greedy_utilitarian_welfare(
        instance,
        profile,
        sat_class=Cost_Sat,
    )
    print(greedy)
    print(instance.is_feasible(greedy))
    print(instance.is_exhaustive(greedy))

    # RESULT_ALL["Integer Linear Program"] = get_all_relax(instance, profile)
    # RESULT_ALL["Equal Shares"] = get_all_relax(instance, profile, mes_computed, exhaustive=False)
    RESULT_ALL["Greedy Utilitarian Welfare"] = get_all_relax(instance, profile, greedy, exhaustive=False)

    with open(f"results5/{Path(file_path).stem}.json", "w") as file:
        s = json.dumps(
            RESULT_ALL,
            sort_keys=True,
            indent=4
        )
        file.write(s)

import os, operator, sys

if __name__ == "__main__":
    # dirpath = os.path.abspath("approval_data")
    # all_files = (os.path.join(basedir, filename) for basedir, dirs, files in os.walk(dirpath) for filename in files)
    # sorted_files = sorted(all_files, key=os.path.getsize)
    # for f in sorted_files:
    #     # print(f)
    #     main_main(f)

    # main_main("approval_data\poland_zabrze_2020_zandka.pb")
    # main_main("approval_data\poland_zabrze_2021_konczyce.pb")
    main_main("approval_data\poland_gdansk_2020_.pb")