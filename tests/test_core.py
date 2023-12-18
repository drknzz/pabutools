"""
Module testing the core.
"""
from unittest import TestCase

from pabutools.analysis.core import core, is_in_core
from pabutools.election import Project, Instance, Cardinality_Sat, ApprovalProfile, ApprovalBallot


class TestCore(TestCase):
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

    def test_is_in_core_approval(self):
        """
        Test checking whether a budget_allocation is in core for approval profile.
        """
        allocation = self.p[1:4] + self.p[7:]
        self.assertFalse(is_in_core(self.instance, self.profile, Cardinality_Sat, allocation))

        allocation = self.p[1:9] + self.p[10:12] + self.p[13:15]
        self.assertTrue(is_in_core(self.instance, self.profile, Cardinality_Sat, allocation))

    def test_core_approval(self):
        """
        Test finding core for approval profile.
        """

        # +----+----+----+-----+
        # | c3 | c4 | c7 | c10 |
        # +--------------+-----+
        # |    c2   | c6 | c9  |
        # +---------+----+-----+
        # |    c1   | c5 | c8  |
        # +====================+
        # | v1 | v2 | v3 | v4  |

        p = [Project(str(i), cost=1) for i in range(11)]
        instance = Instance(p[1:], budget_limit=8)

        v1 = ApprovalBallot({p[1], p[2], p[3]})
        v2 = ApprovalBallot({p[1], p[2], p[4]})
        v3 = ApprovalBallot({p[5], p[6], p[7]})
        v4 = ApprovalBallot({p[8], p[9], p[10]})

        profile = ApprovalProfile(init=[v1, v2, v3, v4])

        core_size = 0
        for budget_allocation in core(instance, profile, Cardinality_Sat):
            core_size += 1
            self.assertTrue(is_in_core(instance, profile, Cardinality_Sat, budget_allocation))

        self.assertEqual(core_size, 39)
