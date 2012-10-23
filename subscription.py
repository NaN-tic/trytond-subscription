# This file is part of subscription module of Tryton.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from datetime import datetime

__all__ = ['SubscriptionDocument',
    'SubscriptionDocumentField',
    'SubscriptionSubscription',
    'SubscriptionSubscriptionHistory',
]


class SubscriptionDocument(ModelSQL, ModelView):
    "Subscription Document"
    __name__ = "subscription.document"

    name = fields.Char('Name', select=True, required=True)
    active = fields.Boolean('Active', select=True,
            help="If the active field is set to False, it will allow you to " \
                "hide the subscription document without removing it.")
    model = fields.Many2One('ir.model', 'Object', required=True)
    fields = fields.One2Many('subscription.document.field', 'document',
            'Fields')

    @classmethod
    def __setup__(cls):
        super(SubscriptionDocument, cls).__setup__()
        cls._error_messages.update({
            'error': 'Error',
            'error_writing_document':
                'You can\'t modify the object linked to this document!\n' \
                'Please, create another document instead!'
        })

    @staticmethod
    def default_active():
        return True

    @classmethod
    def write(cls, documents, vals):
        if vals.has_key('model'):
            cls.raise_user_error(error="error",
                error_description="error_writing_document")
        return super(SubscriptionDocument, cls).write(documents, vals)


class SubscriptionDocumentField(ModelSQL, ModelView):
    "Subscription Document Field"
    __name__ = "subscription.document.field"
    _rec_name = 'field'

    document = fields.Many2One('subscription.document',
            'Subscription Document', ondelete='CASCADE', select=True)
    field = fields.Many2One('ir.model.field', 'Field',
            domain=[('model', '=',
                     Eval('_parent_document', {}).get('model', 0))],
            select=True, required=True)
    value = fields.Char('Default Value', required=True,
        help="Default value is considered for field when new document is " \
            "generated. You must put here a Python expression.")


class SubscriptionSubscription(ModelSQL, ModelView):
    "Subscription"
    __name__ = "subscription.subscription"

    name = fields.Char('Name', select=True, required=True, translate=True)
    user = fields.Many2One('res.user', 'User', required=True,
        domain=[('active', '=', False)])
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help="The user who will receive requests in case of failure")
    active = fields.Boolean('Active', select=True,
            help="If the active field is set to False, it will allow you to " \
                "hide the subscription document without removing it.")
    party = fields.Many2One('party.party', 'Party')
    interval = fields.Integer('Interval Qty')
    interval_type = fields.Selection([
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
        ], 'Interval Unit')
    exec_init = fields.Integer('Number of documents')
    date_init = fields.DateTime('First Date')
    state = fields.Selection([
            ('draft','Draft'),
            ('running','Running'),
            ('done','Done')], 'State', readonly=True)
    doc_source = fields.Reference('Source Document',
            selection='get_document_types', depends=['state'],
            states={'readonly': Eval('state') == 'running'},
            help='User can choose the source document on which he wants to create documents')
    doc_lines = fields.One2Many('subscription.subscription.history',
            'subscription', 'Documents created', readonly=True)
    cron = fields.Many2One('ir.cron', 'Cron Job', 
            help="Scheduler which runs on subscription")
    notes = fields.Text('Notes')
    note = fields.Text('Notes', help="Description or Summary of Subscription")

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

    @staticmethod
    def default_date_init():
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
    def default_interval():
        return 1

    @staticmethod
    def default_interval_type():
        return 'months'

    @staticmethod
    def default_doc_source():
        return False

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def get_document_types(cls):
        cr = Transaction().cursor
        cr.execute('''\
            SELECT
                m.model,
                s.name
            FROM
                subscription_document s,
                ir_model m
            WHERE
                s.model = m.id
            ORDER BY
                s.name
        ''')
        res = [('', '')]
        for model, name in cr.fetchall():
            res.append((model, name))
        return res

    def set_process(self):
        values = {
            'model': self.__name__,
            'name': self.name,
            'user': self.user.id,
            'request_user': self.request_user.id,
            'interval_number': self.interval,
            'interval_type': self.interval_type,
            'number_calls': self.exec_init or 0,
            'next_call': self.date_init,
            'args': repr([self.id]),
            'function': 'model_copy',
        }
        Cron = Pool().get('ir.cron')
        cron = Cron.create(values)
        vals = {
            'cron': cron,
            'state': 'running',
        }
        self.write([self], vals)
#        return True

    def model_copy(self):
        if self.cron:
            Cron = Pool().get('ir.cron')
            remaining = Cron.browse([self.cron.id])[0].number_calls

    def set_done(self):
        pass

    def set_draft(self):
        pass


class SubscriptionSubscriptionHistory(ModelSQL, ModelView):
    "Subscription History"
    __name__ = "subscription.subscription.history"
    _rec_name = 'date'

    date = fields.DateTime('First Date')
    subscription = fields.Many2One('subscription.subscription',
            'Subscription', ondelete='CASCADE')
    document = fields.Reference('Source Document', selection=[
            ('account.invoice', 'Invoice'),
            ('sale.sale', 'Sale Order')], required=True)
    
