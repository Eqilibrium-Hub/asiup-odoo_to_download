from odoo.exceptions import ValidationError
from odoo import _, models
import requests
import json
import base64
import logging

logging.basicConfig(level=logging.INFO)


class PayPalConfigs():
    url_paypal_live = 'https://api.paypal.com'
    url_paypal_sandbox = 'https://api.sandbox.paypal.com'
    end_point_webhooks = '/v1/notifications/webhooks'
    end_point_get_token = '/v1/oauth2/token'
    base_url = 'https://devvn.asiup.suplo.vn'
    end_point_webhook_listen = '/paypal_webhook_00'
    webhook_events_dispute_tracked = ['CUSTOMER.DISPUTE.CREATED', 'CUSTOMER.DISPUTE.RESOLVED',
                                      'CUSTOMER.DISPUTE.UPDATED',
                                      'RISK.DISPUTE.CREATED']
    dispute_detail = '/v1/customer/disputes/'
    webhook_simulate_event = '/v1/notifications/simulate-event'

    # @staticmethod
    # def get_paypal_url(env):
    #     if env['ir.config_parameter'].sudo().get_param('asiup_paypal_integration.paypal_live_mode'):
    #         return PayPalConfigs.url_paypal_live
    #     else:
    #         return PayPalConfigs.url_paypal_sandbox

    # @staticmethod
    # def create_webhook_event(env, access_token):
    #     body = {"url": PayPalConfigs.base_url + PayPalConfigs.end_point_webhook_listen,
    #             "event_types": [{"name": x} for x in PayPalConfigs.webhook_events_dispute_tracked]}
    #
    #     url = PayPalConfigs.get_paypal_url(env) + PayPalConfigs.end_point_webhooks
    #     response = requests.post(url, headers=PayPalConfigs.get_header_connect(access_token),
    #                              data=json.dumps(body)).json()
    #     PayPalConfigs.check_create_webhook_paypal(response)
    #     return response

    @staticmethod
    def get_access_token_paypal(env, client_id, secret):
        credentials = f"{client_id.strip()}:{secret.strip()}"
        encode_credential = base64.b64encode(credentials.encode('utf-8')).decode('utf-8').replace("\n", "")
        headers = {
            "Authorization": f"Basic {encode_credential}",
            'Accept': 'application/json',
            'Accept-Language': 'en_US',
        }
        body = {
            'grant_type': 'client_credentials',
        }
        url = env.get_paypal_url() + PayPalConfigs.end_point_get_token
        response = requests.post(url, headers=headers, data=body).json()
        PayPalConfigs.check_authorization_paypal(response)
        return response.get('access_token')

    # @staticmethod
    # def delete_webhook(env, access_token, webhook_id):
    #     url = PayPalConfigs.get_paypal_url(env) + PayPalConfigs.end_point_webhooks + '/' + webhook_id
    #     response = requests.delete(url, headers=PayPalConfigs.get_header_connect(access_token), data={})
    #     PayPalConfigs.check_delete_webhook_paypal(response)
    #     return response

    @staticmethod
    def check_authorization_paypal(response):
        if 'access_token' in response:
            return
        elif 'error_description' in response:
            raise ValidationError(response.get('error_description'))
        else:
            raise ValidationError(_('PayPal Access Failed'))

    @staticmethod
    def check_delete_webhook_paypal(response):
        if response.status_code == 204:
            return
        else:
            raise ValidationError(_('Remove webhook failed!'))

    @staticmethod
    def check_create_webhook_paypal(response):
        if 'id' in response:
            return
        elif response.get('name') == 'WEBHOOK_URL_ALREADY_EXISTS':
            raise ValidationError(_('Webhook Paypal already exists!'))
        else:
            raise ValidationError(_('Create webhook failed!'))

    @staticmethod
    def check_webhook_dispute_simulate_events(response):
        if 'dispute_id' in response:
            return
        else:
            raise ValidationError(_('Paypal Dispute events not update!'))

    @staticmethod
    def get_header_connect(access_token):
        return {"Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
                }

    # @staticmethod
    # def dispute_paypal_detail(env, access_token, dispute_id='PP-D-4012'):
    #     url = PayPalConfigs.get_paypal_url(env) + PayPalConfigs.dispute_detail + dispute_id
    #     response = requests.get(url, headers=PayPalConfigs.get_header_connect(access_token), data={}).json()
    #     return response

    # @staticmethod
    # def webhook_request_simulate_event(env, access_token, event_type, resource_version='1.0'):
    #     data = {
    #         "url": PayPalConfigs.base_url + PayPalConfigs.end_point_webhooks,
    #         "event_type": event_type,
    #         "resource_version": resource_version
    #     }
    #     url = PayPalConfigs.get_paypal_url(env) + PayPalConfigs.webhook_simulate_event
    #     response = requests.post(url, header=PayPalConfigs.get_header_connect(access_token), data=data).json()
    #     PayPalConfigs.check_webhook_dispute_simulate_events(response)
    #     return response
