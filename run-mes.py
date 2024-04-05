import time

from pabutools.election import parse_pabulib, Cost_Sat
from pabutools.rules import method_of_equal_shares
instance, profile = parse_pabulib("poland_wieliczka_2023.pb")

start = time.time()
winners = method_of_equal_shares(
    instance,
    profile,
    sat_class=Cost_Sat,
    voter_budget_increment=1 # use the completion method Add1
)
print(winners)

print(time.time() - start)
