"""
Module testing the core.
"""
from unittest import TestCase

from pabutools.analysis.core import core_approval, is_in_core_approval
from pabutools.election import Project, Instance, FrozenApprovalBallot, Cardinality_Sat, ApprovalProfile


class TestCore(TestCase):
    @classmethod
    def setUpClass(cls):
        # Example from https://arxiv.org/pdf/1911.11747.pdf page 2

        cls.p = p = [Project(str(i), cost=1) for i in range(16)]
        cls.instance = Instance(p[1:], budget_limit=12)

        v1 = FrozenApprovalBallot({p[1], p[2], p[3], p[4]})
        v2 = FrozenApprovalBallot({p[1], p[2], p[3], p[5]})
        v3 = FrozenApprovalBallot({p[1], p[2], p[3], p[6]})
        v4 = FrozenApprovalBallot({p[7], p[8], p[9]})
        v5 = FrozenApprovalBallot({p[10], p[11], p[12]})
        v6 = FrozenApprovalBallot({p[13], p[14], p[15]})
        cls.profile = ApprovalProfile(ballot_type=FrozenApprovalBallot, init=[v1, v2, v3, v4, v5, v6])

    def test_is_in_core_approval(self):
        """
        Test checking whether a committee is in core for approval profile.
        """
        allocation = self.p[1:4] + self.p[7:]
        self.assertFalse(is_in_core_approval(self.instance, self.profile, Cardinality_Sat, allocation))

        allocation = self.p[1:9] + self.p[10:12] + self.p[13:15]
        self.assertTrue(is_in_core_approval(self.instance, self.profile, Cardinality_Sat, allocation))

    def test_core_approval(self):
        """
        Test finding core for approval profile.
        """

        p = [Project(str(i), cost=1) for i in range(11)]
        instance = Instance(p[1:], budget_limit=8)

        v1 = FrozenApprovalBallot({p[1], p[2], p[3]})
        v2 = FrozenApprovalBallot({p[1], p[2], p[4]})
        v3 = FrozenApprovalBallot({p[5], p[6], p[7]})
        v4 = FrozenApprovalBallot({p[8], p[9], p[10]})

        profile = ApprovalProfile(ballot_type=FrozenApprovalBallot, init=[v1, v2, v3, v4])

        core = core_approval(instance, profile, Cardinality_Sat)
        for committee in core:
            self.assertTrue(is_in_core_approval(instance, profile, Cardinality_Sat, committee))
