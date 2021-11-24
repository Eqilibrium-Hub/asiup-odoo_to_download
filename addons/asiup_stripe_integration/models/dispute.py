from odoo import api, fields, models, _
from datetime import datetime

STRIPE_ISSUING_WEBHOOK_EVENTS = [
    'issuing_dispute.created',
    'issuing_dispute.updated',
    'issuing_dispute.submitted',
    'issuing_dispute.funds_reinstated',
    'issuing_dispute.closed']

STRIPE_PAYMENT_WEBHOOK_EVENTS = [
    'charge.dispute.created',
    'charge.dispute.updated',
    'charge.dispute.funds_withdrawn',
    'charge.dispute.funds_reinstated',
    'charge.dispute.closed']


class Dispute(models.Model):
    _inherit = "dispute"

    dispute_id = fields.Char(string='Dispute ID')

    stripe_state = fields.Selection([
        ('warning_needs_response', u'Warning Needs Response'),
        ('warning_under_review', u'Warning Under Review'),
        ('warning_closed', u'Warning Closed'),
        ('needs_response', u'Needs Response'),
        ('under_review', u'Under Review'),
        ('charge_refunded', u'Charge Refunded'),
        ('won', u'Won'),
        ('lost', u'Lost'),

    ], string='Status', default='needs_response', tracking=1)

    stripe_reason = fields.Selection([
        ('bank_cannot_process', u'Bank Cannot Process'),
        ('check_returned', u'Check Returned'),
        ('credit_not_processed', u'Credit not processed'),
        ('customer_initiated', u'Customer Initiated'),
        ('debit_not_authorized', u'Debit Not Authorized'),
        ('duplicate', u'Duplicate'),
        ('fraudulent', u'Fraudulent'),
        ('general', u'General'),
        ('incorrect_account_details', u'Incorrect Account Details'),
        ('insufficient_funds', u'Insufficient Funds'),
        ('product_not_received', u'Product Not Received'),
        ('product_unacceptable', u'Product Unacceptable'),
        ('subscription_cancelled', u'Subscription Cancelled'),
        ('unrecognized', u'Unrecognized')], string='Payment Dispute Reason', tracking=1)
    amount = fields.Float(string='Amount')
    balance_transactions = fields.Char()
    charge = fields.Char()
    currency = fields.Char()
    created = fields.Datetime(string='Created')
    livemode = fields.Boolean(string='Live Mode')
    payment_intent = fields.Char()
    account_stripe_id = fields.Many2one('stripe.account', string='Source')

    def create_dispute(self, vals, source, account_id):
        self.create({
            'dispute_id': vals.get('id'),
            'amount': vals.get('amount'),
            'balance_transactions': vals.get('balance_transactions'),
            'charge': vals.get('charge'),
            'currency': vals.get('currency'),
            'created': datetime.fromtimestamp(vals.get('created')),
            'livemode': vals.get('livemode'),
            'payment_intent': vals.get('payment_intent'),
            'dispute_source': source,
            'account_stripe_id': account_id
        })
        return

    # def _create_or_update_dispute(self, dispute_vals):
    #     for dispute in dispute_vals:
    #         already_dispute_id = self.search([('stripe_dispute', '=', dispute)])
    #         value = dispute_vals[dispute]
    #         if already_dispute_id:
    #             already_dispute_id.write(value)
    #         else:
    #             value.update({'stripe_dispute': dispute})
    #             self.create(value)
    #     return True
    #
    # def _handle_stripe_webhook(self, data):
    #     wh_type = data.get('type')
    #     if wh_type not in (STRIPE_ISSUING_WEBHOOK_EVENTS + STRIPE_PAYMENT_WEBHOOK_EVENTS):
    #         return False
    #
    #     stripe_object = data.get('data', {}).get('object')
    #
    #     dispute_vals = {
    #         stripe_object.get('id'):
    #             {
    #                 'transaction_authorization': stripe_object.get('charge'),
    #                 'amount': stripe_object.get('amount'),
    #                 'stripe_payment_dispute_reason': stripe_object.get('reason'),
    #                 'customer_name': stripe_object.get('evidence', {}).get('customer_name'),
    #                 'customer_email': stripe_object.get('evidence', {}).get('customer_email'),
    #                 'stripe_dispute_state': stripe_object.get('status'),
    #                 'dispute_source': 'stripe',
    #             }}
    #     self._create_or_update_dispute(dispute_vals)
    #     return True
