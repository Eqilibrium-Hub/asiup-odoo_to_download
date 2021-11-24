# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import exception_to_unicode
import stripe

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


class StripeAcount(models.Model):
    _name = 'stripe.account'
    _description = 'Stripe Account'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name')
    active = fields.Boolean(string='Active', default=True)
    email = fields.Char(string='Email', required=True)
    stripe_apikey = fields.Char(string='Stripe Api Key', required=True)
    stripe_webhook_ids = fields.One2many('webhook.stripe', 'account_stripe', string='Webhook listing')
    webhook_id = fields.Char(string='Webhook ID')
    _sql_constraints = [
        ('stripe_account_unique', 'unique(name, stripe_apikey)',
         "Stripe connect already exists."),
    ]

    def set_credential(self):
        stripe.api_key = self.stripe_apikey

    def get_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url')

    def create_webhook_event(self):
        webhook_event = STRIPE_ISSUING_WEBHOOK_EVENTS + STRIPE_PAYMENT_WEBHOOK_EVENTS
        self.set_credential()
        try:
            endpoint = stripe.WebhookEndpoint.create(
                url=self.get_base_url() + f'/v1/{self.name}/webhook',
                enabled_events=webhook_event
            )
        except Exception as e:
            raise UserError(_(str(e)))
        self.write({
            'webhook_id': endpoint.get('id')
        })
        for event in webhook_event:
            self.create_webhook_info(endpoint, event)

    def create_webhook_info(self, endpoint, event):
        self.env['webhook.stripe'].create({
            'account_stripe': self.id,
            'event': event,
            'url': endpoint.get('url'),
            'livemode': endpoint.get('livemode'),
            'secret': endpoint.get('secret'),
            'status': endpoint.get('status'),
            'webhook_id': endpoint.get('id'),
        })

    @api.model
    def create(self, vals):
        res = super(StripeAcount, self).create(vals)
        self.format_username_stripe()
        res.create_webhook_event()
        return res

    def write(self, vals):
        for rec in self:
            rec.format_username_stripe()
            if not self.webhook_id:
                continue
            rec.stripe_webhook_ids.unlink()
            rec.delete_webhook_endpoint()
            if rec.active:
                rec.create_webhook_event()
        return super(StripeAcount, self).write(vals)

    def unlink(self):
        for rec in self:
            rec.stripe_webhook_ids.unlink()
            rec.delete_webhook_endpoint()
        return super(StripeAcount, self).unlink()

    def delete_webhook_endpoint(self):
        self.set_credential()
        response = stripe.WebhookEndpoint.delete(
            self.webhook_id,
        )
        return response.get('deleted')  # boolean

    def format_username_stripe(self):
        if self.name:
            if not self.name.isalnum():
                raise UserError(_('Stripe name is not valid, only letter and number'))

    def sync_dispute_stripe_account(self):
        self.set_credential()
        dispute_list = stripe.Dispute.list()
        for dispute in dispute_list:
            if not self.env['dispute'].search([('dispute_id', '=', dispute.get('id'))]):
                self.env['dispute'].create_dispute(dispute, 'stripe', self.id)


class WebhookStripe(models.Model):
    _name = 'webhook.stripe'

    webhook_id = fields.Char(string='ID')
    account_stripe = fields.Many2one('stripe.account', string='Account')
    event = fields.Char(string='Event')
    livemode = fields.Boolean(string='Live Mode')
    secret = fields.Char(string='Secret')
    url = fields.Char(string='Url')
    status = fields.Char(string='Status')
