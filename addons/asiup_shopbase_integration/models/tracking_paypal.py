from odoo import models, fields
import csv
import requests
import os
import json
import logging

_logger = logging.getLogger(__name__)

PAYPAL_SHIPPING_STATUS = ['CANCELLED', 'DELIVERED', 'LOCAL_PICKUP', 'ON_HOLD', 'SHIPPED', 'SHIPMENT_CREATED',
                          'DROPPED_OFF',
                          'IN_TRANSIT', 'RETURNED', 'LABEL_PRINTED', 'ERROR', 'UNCONFIRMED', 'PICKUP_FAILED',
                          'DELIVERY_DELAYED',
                          'DELIVERY_SCHEDULED', 'DELIVERY_FAILED', 'INRETURN', 'IN_PROCESS', 'NEW', 'VOID', 'PROCESSED',
                          'NOT_SHIPPED']
ORDER_LINE_STATUS_MAP = [
    ('pending', 'ON_HOLD'),
    ('notfound', 'ON_HOLD'),
    ('transit', 'IN_TRANSIT'),
    ('pickup', 'IN_PROCESS'),
    ('delivered', 'DELIVERY_SCHEDULED'),
    ('expired', 'ON_HOLD'),
    ('undelivered', 'DELIVERY_DELAYED'),
    ('exception', 'DELIVERY_DELAYED'),
    ('alert', 'DELIVERY_DELAYED')
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    account_paypal_payment = fields.Many2one('asiup.paypal.integration', string='Paypal Account',tracking=True)

    def paypal_register_create_tracking(self, order_line):
        url_paypal_tracking_register = self.account_paypal_payment.get_paypal_url() + '/v1/shipping/trackers-batch'
        if not order_line.carrier_id.carrier_paypal_code:
            order_line.carrier_id.carrier_paypal_code = 'OTHER'
        headers = self.account_paypal_payment.get_header_api_paypal()
        body = {
            "trackers": [
                {
                    "transaction_id": self.transaction_authorization,
                    "tracking_number": order_line.tracking_number,
                    "status": 'SHIPPED',
                    "carrier": order_line.carrier_id.carrier_paypal_code,
                    "notify_buyer": True
                }
            ]
        }
        response = requests.post(url_paypal_tracking_register, headers=headers, data=json.dumps(body))
        _logger.info(response.text)
        if response.status_code == 200:
            return True
        return False

    def paypal_register_update_tracking(self, order_line):
        url_update_paypal_tracking = self.account_paypal_payment.get_paypal_url() + order_line.endpoint_paypal_tracking
        if not order_line.carrier_id.carrier_paypal_code:
            order_line.carrier_id.carrier_paypal_code = 'OTHER'
        headers = self.account_paypal_payment.get_header_api_paypal()
        body = {
            "transaction_id": self.transaction_authorization,
            "tracking_number": order_line.tracking_number,
            "status": 'SHIPPED',
            "carrier": order_line.carrier_id.carrier_paypal_code,
            # "notify_buyer": True
        }
        response = requests.put(url_update_paypal_tracking, headers=headers, data=json.dumps(body))
        if response.status_code == 204:
            return True
        return False


class TrackingCourier(models.Model):
    _inherit = 'tracking.courier'

    carrier_paypal_code = fields.Char(string='Carrier Paypal Code')

    def get_carrier_paypal_code(self, trackingmore_response, carrier_list):
        carrier = filter(lambda x: x.get('name').lower() == trackingmore_response.get('name').lower() or
                                   x.get('code').lower() == trackingmore_response.get('code').lower(), carrier_list)
        carrier = list(carrier)
        if not carrier:
            return ''
        return carrier[0].get('code')

    def carrier_paypal_from_csv(self):
        # return list of carrier
        with open(os.path.dirname(os.path.dirname(__file__)) + '/static/carrier_paypal.csv', mode='r') as dt:
            reader = csv.reader(dt)
            return [{'name': rows[0], 'code': rows[1]} for rows in reader]
