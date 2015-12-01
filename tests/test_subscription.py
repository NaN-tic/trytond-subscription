# This file is part of the subscription module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class SubscriptionTestCase(ModuleTestCase):
    'Test Subscription module'
    module = 'subscription'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        SubscriptionTestCase))
    return suite
