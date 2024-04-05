import time

from pabutools.analysis.priceability import priceable, is_priceable, find_price_system
from pabutools.election import parse_pabulib, total_cost, Cost_Sat
from pabutools.rules import method_of_equal_shares, exhaustion_by_budget_increase

STABLE = True
# STABLE = False

# relaxation - w przypadku gdy nie ma optymalnego wyniku (feasible)

# testy z przykladami nie obvious, w ktorych budget na chlopka nie jest po prostu instance_budget / n

if __name__ == "__main__":
    # instance, profile = parse_pabulib("poland_wieliczka_2023.pb", sample_size=1000)
    instance, profile = parse_pabulib("poland_wieliczka_2023.pb")
    # instance, profile = parse_pabulib("tests/PaBuLiB/All/poland_lodz_2022_teofilow-wielkopolska.pb")

    start = time.time()
    budget_allocation, voter_budget, payment_functions = priceable(
        instance,
        profile,
        stable=STABLE,
        extra_output=True,
    )

    print()
    for idx, pf in enumerate(payment_functions):
        d = {c: z for c, z in pf.items() if z > 0}
        if d:
            print(f"{idx}: {d}")
    print()
    print(f"--- TIME: {time.time() - start}")
    print(f"--- Allocation: {budget_allocation}")
    print(f"--- Voter budget: {voter_budget}")
    print(f"--- COST: {total_cost(budget_allocation)}")
    print()

    start2 = time.time()
    verified = is_priceable(
        instance,
        profile,
        budget_allocation=budget_allocation,
        voter_budget=voter_budget,
        payment_functions=payment_functions,
        stable=STABLE,
        verbose=True
    )
    print(f"--- TIME: {time.time() - start2}")
    print(f"--- Verified: {verified}")
    print()

    start3 = time.time()
    verified2 = is_priceable(
        instance,
        profile,
        budget_allocation=budget_allocation,
        stable=STABLE,
        verbose=True,
    )
    print(f"--- TIME: {time.time() - start3}")
    print(f"--- Verified: {verified2}")

    static_mes = {17, 19, 20, 24, 25, 26, 29, 32, 33, 34, 36, 39, 40, 41, 42, 43, 46, 56, 58, 6, 60, 61, 62, 69, 7, 70, 71, 74, 88, 9}
    mes = [project for project in instance if int(project.name) in static_mes]
    # start4 = time.time()
    # mes_computed = method_of_equal_shares(
    #     instance,
    #     profile,
    #     sat_class=Cost_Sat,
    #     voter_budget_increment=1  # use the completion method Add1
    # )
    # assert set(mes_computed) == set(mes)
    # res = find_price_system(
    #     instance,
    #     profile,
    #     mes,
    #     stable=STABLE,
    # )
    #
    # print()
    # # print(f"--- TIME: {time.time() - start4}")
    # print(f"--- MES: {mes}")
    # print(f"--- MES DIFF: -{[x for x in mes if x not in budget_allocation]} +{[x for x in budget_allocation if x not in mes]}")
