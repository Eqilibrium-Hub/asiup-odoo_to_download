# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from ..controllers.asiup_paypal import PayPalConfigs
import logging
import base64
import requests
from odoo.exceptions import ValidationError
import json

_logger = logging.getLogger(__name__)


class AsiupPaypal(models.Model):
    _name = 'asiup.paypal.integration'
    _description = 'Asiup Paypal Integration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'user_name'
    _rec_name = 'user_name'

    active = fields.Boolean(string='Active', default=True)
    user_name = fields.Char(string='User Name', required=True)
    client_id = fields.Char(string='Client ID', required=True)
    secret = fields.Char(string='Secret', required=True)
    webhook_id = fields.Char(string='Webhook ID')
    note = fields.Text(string='Note')

    _sql_constraints = [('account_paypal_unique_constraint', 'unique(user_name,client_id,secret)',
                         "Account PayPal already exists")]

    def action_test_connection(self):
        if self.client_id and self.secret:
            if self.get_access_token_paypal():
                if self.webhook_id:
                    self.delete_webhook()
                if self.active:
                    webhook = self.create_webhook_event()
                    self.webhook_id = webhook.get('id')
                # raise ValidationError(_('PayPal Connection Success!'))
                print('ok')

    def delete_webhook(self):
        url = self.get_paypal_url() + PayPalConfigs.end_point_webhooks + '/' + self.webhook_id
        response = requests.delete(url, headers=self.get_header_api_paypal(), data={})
        self.check_delete_webhook_paypal(response)
        return response

    def write(self, vals):
        for rec in self:
            client_id = vals.get('client_id') if vals.get('client_id') else rec.client_id
            secret = vals.get('secret') if vals.get('secret') else rec.secret
            if client_id and secret and 'client_id' in vals or 'secret' in vals:
                if rec.webhook_id:
                    rec.delete_webhook()
                if rec.active:
                    webhook = rec.create_webhook_event()
                    vals.update({
                        'webhook_id': webhook.get('id')
                    })
                else:
                    vals.update({
                        'webhook_id': ''
                    })
        return super(AsiupPaypal, self).write(vals)

    @api.model
    def create(self, vals):
        client_id = vals.get('client_id') if vals.get('client_id') else self.client_id
        secret = vals.get('secret') if vals.get('secret') else self.secret
        if client_id and secret:
            self.get_access_token_paypal()
            if not self.webhook_id:
                webhook = self.create_webhook_event()
                vals.update({
                    'webhook_id': webhook.get('id')
                })
        return super(AsiupPaypal, self).create(vals)

    def unlink(self):
        for record in self:
            if self.webhook_id:
                self.delete_webhook()
        return super(AsiupPaypal, self).unlink()

    def create_webhook_event(self):
        headers = self.get_header_api_paypal()
        body = {"url": PayPalConfigs.base_url + PayPalConfigs.end_point_webhook_listen,
                "event_types": [{"name": x} for x in PayPalConfigs.webhook_events_dispute_tracked]}

        url = self.get_paypal_url() + PayPalConfigs.end_point_webhooks
        response = requests.post(url, headers=headers, data=json.dumps(body)).json()
        self.check_create_webhook_paypal(response)
        return response

    def get_access_token_paypal(self):
        headers = self.get_header_integration_paypal()
        body = {
            'grant_type': 'client_credentials',
        }
        url = self.get_paypal_url() + PayPalConfigs.end_point_get_token
        response = requests.post(url, headers=headers, data=body).json()
        self.check_authorization_paypal(response)
        return response.get('access_token')

    def get_encode_credentials_paypal(self):
        credentials = f"{self.client_id.strip()}:{self.secret.strip()}"
        encode_credential = base64.b64encode(credentials.encode('utf-8')).decode('utf-8').replace("\n", "")
        return encode_credential

    def get_header_integration_paypal(self):
        encode_credential = self.get_encode_credentials_paypal()
        return {
            "Authorization": f"Basic {encode_credential}",
            'Accept': 'application/json',
            'Accept-Language': 'en_US',
        }

    def get_header_api_paypal(self):
        access_token = self.get_access_token_paypal()
        return {
            "Authorization": f"Bearer {access_token}",
            'Content-Type': 'application/json',
        }

    def get_paypal_url(self):
        if self.env['ir.config_parameter'].sudo().get_param('asiup_paypal_integration.paypal_live_mode'):
            return PayPalConfigs.url_paypal_live
        return PayPalConfigs.url_paypal_sandbox

    @staticmethod
    def check_authorization_paypal(response):
        if 'access_token' in response:
            return
        elif 'error_description' in response:
            raise ValidationError(response.get('error_description'))
        else:
            raise ValidationError(_('PayPal Access Failed'))

    @staticmethod
    def check_create_webhook_paypal(response):
        if 'id' in response:
            return
        elif response.get('name') == 'WEBHOOK_URL_ALREADY_EXISTS':
            raise ValidationError(_('Webhook Paypal already exists!'))
        else:
            raise ValidationError(_('Create webhook failed!'))

    @staticmethod
    def check_delete_webhook_paypal(response):
        if response.status_code == 204:
            return
        else:
            raise ValidationError(_('Remove webhook failed!'))
