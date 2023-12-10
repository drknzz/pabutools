"""
Module testing priceability.
"""
from unittest import TestCase

from pabutools.analysis.priceability import is_priceable_approval, priceable_approval, \
    _is_priceable_approval_price_system, _is_priceable_approval_search
from pabutools.election import Project, Instance, FrozenApprovalBallot, Cardinality_Sat, ApprovalProfile
# from pabutools.utils import powerset


class TestPriceability(TestCase):
    @classmethod
    def setUpClass(cls):
        # Example from https://arxiv.org/pdf/1911.11747.pdf page 2

        # +----+----+----+
        # | c4 | c5 | c6 |
        # +----+----+----+----+-----+-----+
        # |      c3      | c9 | c12 | c15 |
        # +--------------+----+-----+-----+
        # |      c2      | c8 | c11 | c14 |
        # +--------------+----+-----+-----+
        # |      c1      | c7 | c10 | c13 |
        # +===============================+
        # | v1 | v2 | v3 | v4 | v5  | v6  |

        cls.p = p = [Project(str(i), cost=1) for i in range(16)]
        cls.instance = Instance(p[1:], budget_limit=12)

        v1 = FrozenApprovalBallot({p[1], p[2], p[3], p[4]})
        v2 = FrozenApprovalBallot({p[1], p[2], p[3], p[5]})
        v3 = FrozenApprovalBallot({p[1], p[2], p[3], p[6]})
        v4 = FrozenApprovalBallot({p[7], p[8], p[9]})
        v5 = FrozenApprovalBallot({p[10], p[11], p[12]})
        v6 = FrozenApprovalBallot({p[13], p[14], p[15]})
        cls.profile = ApprovalProfile(ballot_type=FrozenApprovalBallot, init=[v1, v2, v3, v4, v5, v6])

    def test_is_priceable_approval(self):
        """
        Test checking whether a committee is priceable for approval profile.
        """
        allocation = self.p[1:4] + self.p[7:]
        self.assertFalse(is_priceable_approval(self.instance, self.profile, Cardinality_Sat, allocation))

        allocation = self.p[1:9] + self.p[10:12] + self.p[13:15]
        self.assertTrue(is_priceable_approval(self.instance, self.profile, Cardinality_Sat, allocation))

    def test_is_priceable_approval_extended(self):
        # Example from https://arxiv.org/pdf/1911.11747.pdf page 15 (k = 5)

        # +------------------------+
        # |           c10          |
        # +------------------------+
        # |           c9           |
        # +------------------------+
        # |           c8           |
        # +------------------------+
        # |           c7           |
        # +------------------------+
        # |           c6           |
        # +----+----+----+----+----+
        # | c1 | c2 | c3 | c4 | c5 |
        # +========================+
        # | v1 | v2 | v3 | v4 | v5 |

        # TODO: refactor for better example fixtures
        # TODO: frozenapprovalballot ?
        p = [Project(str(i), cost=1) for i in range(11)]
        instance = Instance(p[1:], budget_limit=5)

        v1 = FrozenApprovalBallot({p[1], p[6], p[7], p[8], p[9], p[10]})
        v2 = FrozenApprovalBallot({p[2], p[6], p[7], p[8], p[9], p[10]})
        v3 = FrozenApprovalBallot({p[3], p[6], p[7], p[8], p[9], p[10]})
        v4 = FrozenApprovalBallot({p[4], p[6], p[7], p[8], p[9], p[10]})
        v5 = FrozenApprovalBallot({p[5], p[6], p[7], p[8], p[9], p[10]})
        profile = ApprovalProfile(ballot_type=FrozenApprovalBallot, init=[v1, v2, v3, v4, v5])

        allocation = p[1:6]
        self.assertTrue(is_priceable_approval(instance, profile, Cardinality_Sat, allocation))

        allocation = p[6:]
        self.assertTrue(is_priceable_approval(instance, profile, Cardinality_Sat, allocation))

        # apparently all committees of size 5 are priceable
        priceable = priceable_approval(instance, profile, Cardinality_Sat, resoluteness=False, extra_output=True)
        for committee, p, pf in priceable:
            self.assertTrue(is_priceable_approval(instance, profile, Cardinality_Sat, committee, p, pf))

    def test_is_priceable_approval_extended2(self):
        # Example from http://www.cs.utoronto.ca/~nisarg/papers/priceability.pdf page 13

        # +--------------+--------------+--------------+
        # |      c6      |      c9      |      c12     |
        # +--------------+--------------+--------------+
        # |      c5      |      c8      |      c11     |
        # +--------------+--------------+--------------+
        # |      c4      |      c7      |      c10     |
        # +--------------+--------------+--------------+
        # |                     c3                     |
        # +--------------------------------------------+
        # |                     c2                     |
        # +--------------------------------------------+
        # |                     c1                     |
        # +============================================+
        # | v1 | v2 | v3 | v4 | v5 | v6 | v7 | v8 | v9 |

        # TODO: refactor for better example fixtures
        # TODO: frozenapprovalballot ?
        p = [Project(str(i), cost=1) for i in range(13)]
        instance = Instance(p[1:], budget_limit=9)

        v1 = FrozenApprovalBallot({p[1], p[2], p[3], p[4], p[5], p[6]})
        v2 = FrozenApprovalBallot({p[1], p[2], p[3], p[4], p[5], p[6]})
        v3 = FrozenApprovalBallot({p[1], p[2], p[3], p[4], p[5], p[6]})

        v4 = FrozenApprovalBallot({p[1], p[2], p[3], p[7], p[8], p[9]})
        v5 = FrozenApprovalBallot({p[1], p[2], p[3], p[7], p[8], p[9]})
        v6 = FrozenApprovalBallot({p[1], p[2], p[3], p[7], p[8], p[9]})

        v7 = FrozenApprovalBallot({p[1], p[2], p[3], p[10], p[11], p[12]})
        v8 = FrozenApprovalBallot({p[1], p[2], p[3], p[10], p[11], p[12]})
        v9 = FrozenApprovalBallot({p[1], p[2], p[3], p[10], p[11], p[12]})
        profile = ApprovalProfile(ballot_type=FrozenApprovalBallot, init=[v1, v2, v3, v4, v5, v6, v7, v8, v9])

        allocation = p[1:10]
        self.assertTrue(is_priceable_approval(instance, profile, Cardinality_Sat, allocation))

        allocation = p[1:6] + p[7:9] + p[10:12]
        self.assertTrue(is_priceable_approval(instance, profile, Cardinality_Sat, allocation))

        # TODO: verify manually that it is for sure not priceable
        allocation = p[1:6] + p[7:9] + p[11:12]
        self.assertFalse(is_priceable_approval(instance, profile, Cardinality_Sat, allocation))

        # again, apparently all committees of size 9 are priceable
        priceable = priceable_approval(instance, profile, Cardinality_Sat, resoluteness=False, extra_output=True)
        for committee, p, pf in priceable:
            self.assertTrue(is_priceable_approval(instance, profile, Cardinality_Sat, committee, p, pf))

    def test_priceable_approval(self):
        """
        Test finding core for approval profile.
        """
        priceable, p, pf = priceable_approval(self.instance, self.profile, sat_class=None, extra_output=True)  # TODO: sat class
        self.assertTrue(
            _is_priceable_approval_price_system(
                self.instance,
                self.profile,
                sat_class=None,
                committee=priceable,
                candidate_price=p,
                payment_functions=pf
            )
        )

        priceable = priceable_approval(self.instance, self.profile, sat_class=None)  # TODO: sat class
        self.assertTrue(
            _is_priceable_approval_search(
                self.instance,
                self.profile,
                sat_class=None,
                committee=priceable,
            )
        )

        priceable_committees = priceable_approval(self.instance, self.profile, sat_class=None, resoluteness=False, extra_output=True)
        for priceable, p, pf in priceable_committees:
            self.assertTrue(
                _is_priceable_approval_price_system(
                    self.instance,
                    self.profile,
                    sat_class=None,
                    committee=priceable,
                    candidate_price=p,
                    payment_functions=pf
                )
            )

        # for committee in powerset(self.instance):
        #     priceable = is_priceable_approval(
        #         self.instance,
        #         self.profile,
        #         sat_class=None,
        #         committee=committee,
        #     )
        #     if list(committee) in priceable_committees:
        #         self.assertTrue(priceable)
        #     else:
        #         self.assertFalse(priceable)
