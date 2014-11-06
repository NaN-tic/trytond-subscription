# This file is part of subscription module of Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import datetime
from trytond.config import config
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools import safe_eval
from trytond.transaction import Transaction
import contextlib
import logging

__all__ = ['SubscriptionSubscription', 'SubscriptionLine', 'SubscriptionHistory']

STATES = {
    'readonly': Eval('state') == 'running',
}
DEPENDS = ['state']


class SubscriptionSubscription(ModelSQL, ModelView):
    'Subscription'
    __name__ = 'subscription.subscription'

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

    name = fields.Char('Name', select=True, required=True, states=STATES)
    user = fields.Many2One('res.user', 'User', required=True,
        domain=[('active', '=', False)], states=STATES)
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True, states=STATES,
        help='The user who will receive requests in case of failure.')
    request_group = fields.Many2One('res.group', 'Request Group',
        required=True, states=STATES,
        help='The group who will receive requests.')
    active = fields.Boolean('Active', select=True, states=STATES,
            help='If the active field is set to False, it will allow you to ' \
                'hide the subscription without removing it.')
    interval_number = fields.Integer('Interval Qty', states=STATES)
    interval_type = fields.Selection([
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
        ], 'Interval Unit', states=STATES)
    number_calls = fields.Integer('Number of documents', states=STATES)
    next_call = fields.DateTime('First Date', states=STATES)
    state = fields.Selection([
            ('draft','Draft'),
            ('running','Running'),
            ('done','Done')], 'State', readonly=True, states=STATES)
    model_source = fields.Reference('Source Document',
            selection='get_model', depends=['state'],
            help='User can choose the source model on which he wants to ' \
                'create models.', states=STATES)
    lines = fields.One2Many('subscription.line', 'subscription', 'Lines',
            states=STATES)
    history = fields.One2Many('subscription.history',
            'subscription', 'History', states=STATES)
    cron = fields.Many2One('ir.cron', 'Cron Job', states=STATES,
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
            'error_creating': 'Error creating document \'%s\'',
            'created_successfully': 'Document \'%s\' created successfully',
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

    @classmethod
    @ModelView.button
    def set_process(self, subscriptions):
        RequestLink = Pool().get('res.request.link')
        to_create = []
        for subscription in subscriptions:
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
                cron = Cron.create([vals])[0]
            else:
                vals['active'] = True
                Cron.write(cron, vals)
                cron = cron[0]
            vals = {
                'cron': cron.id,
                'state': 'running',
            }
            self.write([subscription], vals)

            # Add a res.request.link record to allow linking the documents copied
            # in requests created
            request_link = RequestLink.search([
                    ('model', '=', subscription.model_source.__name__),
                ])
            if not request_link:
                Model = Pool().get('ir.model')
                model = Model.search([
                        ('model', '=', subscription.model_source.__name__),
                    ])
                to_create.append({
                    'model': subscription.model_source.__name__,
                    'priority': 5,
                    'name': model and model[0] and model[0].name or False,
                })
        if to_create:
            RequestLink.create(to_create)

    @classmethod
    def model_copy(cls, subscription_id):
        logging.getLogger('subscription').info(
            'Running subscription ID %s' % (subscription_id))

        Cron = Pool().get('ir.cron')
        History = Pool().get('subscription.history')
        subscription = cls(subscription_id)
        logger = logging.getLogger('subscription_subscription')
        remaining = Cron.browse([subscription.cron.id])[0].number_calls
        model_id = subscription.model_source and subscription.model_source.id \
                or False
        if model_id:
            context = Transaction().context.copy()
            Model = Pool().get(subscription.model_source.__name__)
            Request = Pool().get('res.request')
            default = {'state':'draft'}
            context = {
                'self': subscription,
                'pool': Pool(),
                'transaction': Transaction(),
            }
            req_vals = {
                'act_from': subscription.user.id,
                'date_sent': datetime.now(),
                'state': 'waiting',
                'trigger_date': datetime.now(),
            }

            # Map subscription lines and create a copy of the document
            # and save logs in subscription.history model
            for line in subscription.lines:
                default[line.field.name] = safe_eval(line.value, context)
            try:
                model = Model.copy([subscription.model_source], default)
            except:
                history_vals = {
                    'log': cls.raise_user_error(
                        error='error_creating',
                        error_args=subscription.model_source.__name__,
                        raise_exception=False),
                    'subscription': subscription,
                }
                req_vals['name'] = cls.raise_user_error(
                        error='error_creating',
                        error_args=subscription.name,
                        raise_exception=False)
                req_vals['body'] = cls.raise_user_error(
                        error='error_creating',
                        error_args=subscription.model_source.__name__,
                        raise_exception=False)
                req_vals['priority'] = '2'
            else:
                history_vals = {
                    'log': cls.raise_user_error(
                        error='created_successfully',
                        error_args=subscription.model_source.__name__,
                        raise_exception=False),
                    'subscription': subscription.id,
                }
                req_vals['name'] = cls.raise_user_error(
                        error='created_successfully',
                        error_args=subscription.name,
                        raise_exception=False)
                req_vals['body'] = cls.raise_user_error(
                        error='created_successfully',
                        error_args=model[0].id,
                        raise_exception=False)
                req_vals['priority'] = '0'
                req_vals['references'] = [
                        ('create', {
                                'reference': '%s,%s' % \
                                (subscription.model_source.__name__,
                                            model[0].id)
                            }
                        )]
            history_vals['document'] = (subscription.model_source.__name__,
                                        model[0].id)
            History.create([history_vals])

            # Send requests to users in request_group
            to_create = []
            for user in subscription.request_group.users:
                if user != subscription.request_user and user.active:
                    language = (user.language.code if user.language
                            else config.get('database', 'language'))
                    with contextlib.nested(Transaction().set_user(user.id),
                            Transaction().set_context(language=language)):
                        req_vals['act_to'] = user.id
                        to_create.append(req_vals)
                        Cron._get_request_values(subscription.cron)
            if to_create:
                Request.create(to_create)

            # If it is the last cron execution, set the state of the
            # subscriptio to done
            if remaining == 1:
                subscription.write([subscription], {'state': 'done'})
            logger.info('End subscription ID %s.' % subscription_id)
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
        self.write(subscriptions, {'state':'draft'})


class SubscriptionLine(ModelSQL, ModelView):
    'Subscription Line'
    __name__ = 'subscription.line'
    _rec_name = 'field'

    subscription = fields.Many2One('subscription.subscription',
            'Subscription', ondelete='CASCADE', select=True)
    field = fields.Many2One('ir.model.field', 'Field',
# TODO domain to filter available fields of the model  model_source of related
# subscription
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
            'As an example to get the current date:\n\n' \
            'pool.get(\'ir.date\').today()')


class SubscriptionHistory(ModelSQL, ModelView):
    "Subscription History"
    __name__ = "subscription.history"
    _rec_name = 'date'

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

    date = fields.DateTime('Date', readonly=True)
    log = fields.Char('Result', readonly=True)
    subscription = fields.Many2One('subscription.subscription',
            'Subscription', ondelete='CASCADE', readonly=True)
    document = fields.Reference('Source Document', selection='get_model',
            readonly=True)

    @staticmethod
    def default_date():
        return datetime.now()
