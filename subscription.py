# This file is part of subscription module of Tryton.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
#from trytond.pool import Pool

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

    @staticmethod
    def default_active():
        return True


class SubscriptionDocumentField(ModelSQL, ModelView):
    "Subscription Document Field"
    __name__ = "subscription.document.field"
    _rec_name = 'field'

    field = fields.Many2One('ir.model.field', 'Field', required=True,
#            domain=[('model', '=', parent.model)],
            select=True)
    value = fields.Selection([
            ('false', 'False'),
            ('date', 'Current'),
        ], 'Default Value', readonly=True, required=True,
        help="Default value is considered for field when new document is " \
            "generated.")
    document = fields.Many2One('subscription.document',
            'Subscription Document', ondelete='CASCADE', select=True)


class SubscriptionSubscription(ModelSQL, ModelView):
    "Subscription"
    __name__ = "subscription.subscription"

    @classmethod
    def get_document_types(cls):
        pass
#        Move = Pool().get('account.move')
#        return Move.get_origin()

    name = fields.Char('Name', select=True, required=True)
    active = fields.Boolean('Active', select=True,
            help="If the active field is set to False, it will allow you to " \
                "hide the subscription document without removing it.")
#    party = fields.Many2One('party.party', 'Party')
    user = fields.Many2One('res.user', 'User', required=True)
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
            ('done','Done')], 'State')
#    doc_source = fields.Reference('Source Document',
#            selection='get_document_types',
#            help='User can choose the source document on which he wants to ' \
#                'create documents')
    doc_lines = fields.One2Many('subscription.subscription.history',
            'subscription', 'Documents created', readonly=True)
    cron = fields.Many2One('ir.cron', 'Cron Job', 
            help="Scheduler which runs on subscription")
    notes = fields.Text('Notes')
    note = fields.Text('Notes', help="Description or Summary of Subscription")

    @staticmethod
    def default_active():
        return True


class SubscriptionSubscriptionHistory(ModelSQL, ModelView):
    "Subscription History"
    __name__ = "subscription.subscription.history"
    _rec_name = 'date'

    date = fields.DateTime('First Date')
    subscription = fields.Many2One('subscription.subscription',
            'Subscription', ondelete='CASCADE')
    document = fields.Reference('Source Document', selection=[
            ('account.invoice', 'Invoice'),
            ('sale.sale', 'Sale Order')])
    
