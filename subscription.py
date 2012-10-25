# This file is part of subscription module of Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from datetime import datetime
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Get, Id
from trytond.transaction import Transaction
import logging

__all__ = [
    'SubscriptionSubscription',
    'SubscriptionLine',
]

STATES = {
    'readonly': ~Eval('state', 'running'),
}
DEPENDS = ['state']

class SubscriptionSubscription(ModelSQL, ModelView):
    'Subscription'
    __name__ = 'subscription.subscription'

    name = fields.Char('Name', select=True, required=True, translate=True)
    user = fields.Many2One('res.user', 'User', required=True,
        domain=[('active', '=', False)])
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help='The user who will receive requests in case of failure.')
    request_group = fields.Many2One(
        'res.group', 'Request Group',
        help='The group who will receive requests in case of failure.')
    active = fields.Boolean('Active', select=True,
            help='If the active field is set to False, it will allow you to ' \
                'hide the subscription without removing it.')
    interval_number = fields.Integer('Interval Qty')
    interval_type = fields.Selection([
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
        ], 'Interval Unit')
    number_calls = fields.Integer('Number of documents')
    next_call = fields.DateTime('First Date')
    state = fields.Selection([
            ('draft','Draft'),
            ('running','Running'),
            ('done','Done')], 'State', readonly=True)
    model_source = fields.Reference('Source Document',
            selection='get_model', depends=['state'],
            states={'readonly': Eval('state') == 'running'},
            help='User can choose the source model on which he wants to ' \
                'create models.')
    lines = fields.One2Many('subscription.line', 'subscription', 'Lines')
    cron = fields.Many2One('ir.cron', 'Cron Job', 
            help='Scheduler which runs on subscription.', ondelete='CASCADE')
    note = fields.Text('Notes', help='Description or Summary of Subscription.')

    @classmethod
    def __setup__(cls):
        super(SubscriptionSubscription, cls).__setup__()
        cls._buttons.update({
            'set_process': {
                'invisible': Eval('state') != 'draft',
                },
            'set_done': {
                'invisible': Eval('state') != 'running',
                },
            'set_draft': {
                'invisible': Eval('state') != 'done',
                },
            })
        cls._error_messages.update({
            'error': 'Error. Wrong Source Document',
            'provide_another_source': 'Please provide another source ' \
                'model.\nThis one does not exist!',
            })
        cls._sql_constraints = [
            ('name_unique', 'UNIQUE(name)',
             'The name of the subscription must be unique!')
        ]

    @staticmethod
    def default_next_call():
        return datetime.now()

    @staticmethod
    def default_user():
        User = Pool().get('res.user')
        user_ids = User.search([
                ('active', '=', False),
                ('login', '=', 'user_cron_trigger'),
            ])
        return user_ids[0].id

    @staticmethod
    def default_request_user():
        return Transaction().user

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_interval_number():
        return 1

    @staticmethod
    def default_number_calls():
        return 1

    @staticmethod
    def default_interval_type():
        return 'months'

    @staticmethod
    def default_model_source():
        return False

    @staticmethod
    def default_state():
        return 'draft'
#
    @classmethod
    def get_model(cls):
        cr = Transaction().cursor
        cr.execute('''\
            SELECT
                m.model,
                m.name
            FROM
                ir_model m
            ORDER BY
                m.name
        ''')
        return cr.fetchall()

    @classmethod
    @ModelView.button
    def set_process(self, subscriptions):
        for subscription in subscriptions:
            prova = str([subscription])
            prova2 = repr
            vals = {
                'model': subscription.__name__,
                'name': subscription.name,
                'user': subscription.user.id,
                'request_user': subscription.request_user.id,
                'interval_number': subscription.interval_number,
                'interval_type': subscription.interval_type,
                'number_calls': subscription.number_calls or 1,
                'next_call': subscription.next_call,
                'args': str([subscription.id]),
                'function': 'model_copy',
            }
            Cron = Pool().get('ir.cron')
            domain = [
                ('model', '=', subscription.__name__),
                ('name', '=', subscription.name),
                ('active', '=', False),
            ]
            cron = Cron.search([domain])
            if not cron:
                cron = Cron.create(vals)
            else:
                vals['active'] = True
                Cron.write(cron, vals)
                cron = cron[0]
            vals = {
                'cron': cron.id,
                'state': 'running',
            }
            self.write([subscription], vals)

    @classmethod
    def model_copy(cls, subscription_id=None):


        Cron = Pool().get('ir.cron')
        subscription = cls(subscription_id)


        logger = logging.getLogger('subscription_subscription')
        remaining = Cron.browse([subscription.cron.id])[0].number_calls
        model_id = subscription.model_source and subscription.model_source.id \
                or False
        if model_id:
            Model = Pool().get(subscription.model_source.__name__)
            default = {'state':'draft'}
            localspace = {
                'self': subscription,
                'pool': Pool(),
                'transaction': Transaction(),
            }
            for line in subscription.lines:
                with Transaction().set_context():
                    try:
                        exec line.value in localspace
                    except SyntaxError, e:
                        logger.error('Syntax Error in field %s.\n'\
                                'Error: %s' % (line.field.name, e))
                        return None
                    except NameError, e:
                        logger.error('Syntax Error in field %s.\n'\
                                'Error: %s' % (line.field.name, e))
                        return None
                    except Exception, e:
                        logger.error('Unkonwn Error in field %s.'\
                                '\nMessage: %s' % (line.field.name, e))
                        return None
                    default[line.field.name] = localspace['result'] \
                            if 'result' in localspace else False
            model_id = Model.copy([subscription.model_source], default)
            if remaining == 1:
                subscription.write([subscription.id], {'state': 'done'})
        else:
            logger.error('Document in subscription %s not found.\n' % \
                         subscription.name)

    @classmethod
    @ModelView.button
    def set_done(self, subscriptions):
        for subscription in subscriptions:
            Pool().get('ir.cron').write([subscription.cron], {'active': False})
            self.write([subscription], {'state':'draft'})

    @classmethod
    @ModelView.button
    def set_draft(self, subscriptions):
        self.write([self], {'state':'draft'})


class SubscriptionLine(ModelSQL, ModelView):
    'Subscription Line'
    __name__ = 'subscription.line'
    _rec_name = 'field'

    subscription = fields.Many2One('subscription.subscription',
            'Subscription', ondelete='CASCADE', select=True)
#    name = fields.Many2One('ir.model.field', 'Field',
#            domain=[('model', '=',
#                     Id(Eval('_parent_subscription', {}), 'model_source')
#                )],
#            select=True, required=True)
    field = fields.Many2One('ir.model.field', 'Field',
#        domain=[(
#            'model', '=', Eval('_parent_subscription', {}).get('model_source')
#        )],
        select=True, required=True)
    value = fields.Char('Default Value', required=True,
        help='Default value is considered for field when new subscription ' \
            'is generated. You must put here a Python expression. The ' \
            'available variables are:\n' \
            '  - self: The current subcription object.\n' \
            '  - pool: The store of the instances of models.\n' \
            '  - transaction: That contains thread-local parameters of the ' \
            'database transaction.\n' \
            'You must return a value into a variable called "result".\n' \
            'As an example to get the current date:\n\n' \
            'result = pool.get(\'ir.date\').today()')


