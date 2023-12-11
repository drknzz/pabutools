"""
Module testing priceability.
"""
import math
from unittest import TestCase

from pabutools.analysis.priceability import is_priceable, priceable
from pabutools.election import Project, Instance, ApprovalProfile, ApprovalBallot


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

        v1 = ApprovalBallot({p[1], p[2], p[3], p[4]})
        v2 = ApprovalBallot({p[1], p[2], p[3], p[5]})
        v3 = ApprovalBallot({p[1], p[2], p[3], p[6]})
        v4 = ApprovalBallot({p[7], p[8], p[9]})
        v5 = ApprovalBallot({p[10], p[11], p[12]})
        v6 = ApprovalBallot({p[13], p[14], p[15]})
        cls.profile = ApprovalProfile(init=[v1, v2, v3, v4, v5, v6])

    def test_is_priceable_approval(self):
        """
        Test checking whether a committee is priceable for approval profile.
        """
        allocation = self.p[1:4] + self.p[7:]
        self.assertFalse(is_priceable(self.instance, self.profile, allocation, stable=True))

        allocation = self.p[1:9] + self.p[10:12] + self.p[13:15]
        self.assertTrue(is_priceable(self.instance, self.profile, allocation, stable=True))

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

        p = [Project(str(i), cost=1) for i in range(11)]
        instance = Instance(p[1:], budget_limit=5)

        v1 = ApprovalBallot({p[1], p[6], p[7], p[8], p[9], p[10]})
        v2 = ApprovalBallot({p[2], p[6], p[7], p[8], p[9], p[10]})
        v3 = ApprovalBallot({p[3], p[6], p[7], p[8], p[9], p[10]})
        v4 = ApprovalBallot({p[4], p[6], p[7], p[8], p[9], p[10]})
        v5 = ApprovalBallot({p[5], p[6], p[7], p[8], p[9], p[10]})
        profile = ApprovalProfile(init=[v1, v2, v3, v4, v5])

        allocation = p[1:6]
        self.assertFalse(is_priceable(instance, profile, allocation, stable=True))

        allocation = p[6:]
        self.assertTrue(is_priceable(instance, profile, allocation, stable=True))

        priceable_allocations = priceable(instance, profile, stable=True, resoluteness=False, extra_output=True)
        for committee, p, pf in priceable_allocations:
            self.assertTrue(is_priceable(instance, profile, committee, p, pf, stable=True))

        self.assertEqual(len(priceable_allocations), 1)

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

        p = [Project(str(i), cost=1) for i in range(13)]
        instance = Instance(p[1:], budget_limit=9)

        v1 = ApprovalBallot({p[1], p[2], p[3], p[4], p[5], p[6]})
        v2 = ApprovalBallot({p[1], p[2], p[3], p[4], p[5], p[6]})
        v3 = ApprovalBallot({p[1], p[2], p[3], p[4], p[5], p[6]})

        v4 = ApprovalBallot({p[1], p[2], p[3], p[7], p[8], p[9]})
        v5 = ApprovalBallot({p[1], p[2], p[3], p[7], p[8], p[9]})
        v6 = ApprovalBallot({p[1], p[2], p[3], p[7], p[8], p[9]})

        v7 = ApprovalBallot({p[1], p[2], p[3], p[10], p[11], p[12]})
        v8 = ApprovalBallot({p[1], p[2], p[3], p[10], p[11], p[12]})
        v9 = ApprovalBallot({p[1], p[2], p[3], p[10], p[11], p[12]})
        profile = ApprovalProfile(init=[v1, v2, v3, v4, v5, v6, v7, v8, v9])

        allocation = p[4:13]
        self.assertFalse(is_priceable(instance, profile, allocation, stable=True))

        allocation = p[1:10]
        self.assertTrue(is_priceable(instance, profile, allocation, stable=True))

        allocation = p[1:6] + p[7:9] + p[10:12]
        self.assertTrue(is_priceable(instance, profile, allocation, stable=True))

        # size 8
        allocation = p[1:6] + p[7:9] + p[11:12]
        self.assertTrue(is_priceable(instance, profile, allocation, stable=True))

        priceable_allocations = priceable(instance, profile, stable=True, resoluteness=False, extra_output=True)
        for committee, p, pf in priceable_allocations:
            self.assertTrue(is_priceable(instance, profile, committee, p, pf, stable=True, verbose=True))

        # choose c1, c2, c3 and 6 from the rest
        self.assertEqual(len(priceable_allocations), math.comb(9, 6))

    def test_priceable_approval(self):
        """
        Test finding core for approval profile.
        """
        priceable_allocation, p, pf = priceable(self.instance, self.profile, stable=True, extra_output=True)
        self.assertTrue(
            is_priceable(
                self.instance,
                self.profile,
                committee=priceable_allocation,
                candidate_price=p,
                payment_functions=pf,
                stable=True,
            )
        )

        priceable_allocation = priceable(self.instance, self.profile, stable=True)
        self.assertTrue(
            is_priceable(
                self.instance,
                self.profile,
                committee=priceable_allocation,
                stable=True,
            )
        )

        priceable_committees = priceable(self.instance, self.profile, stable=True, resoluteness=False, extra_output=True)
        for priceable_allocation, p, pf in priceable_committees:
            self.assertTrue(
                is_priceable(
                    self.instance,
                    self.profile,
                    committee=priceable_allocation,
                    candidate_price=p,
                    payment_functions=pf,
                    stable=True
                )
            )
