# This file is part of subscription module of Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.pool import Pool
from .subscription import *


def register():
    Pool.register(
        SubscriptionSubscription,
        SubscriptionLine,
        SubscriptionHistory,
        module='subscription', type_='model')
