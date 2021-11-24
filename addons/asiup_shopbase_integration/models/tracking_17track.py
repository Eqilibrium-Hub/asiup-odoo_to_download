from odoo import models, fields, api, _
import requests
import json
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_Exception = {
    200: 'The request is processed normally.',
    401: 'Request unauthorized, wrong key, access IP not in whitelist or account disabled.',
    404: 'The requested URL address is incorrect.',
    429: 'Access frequency exceeds limit.',
    500: 'Server Error.',
    503: 'Service temporarily unavailable.'}

track17_ffm_status = {
    0: 'notfound',
    10: 'transit',
    20: 'expired',
    30: 'pickup',
    35: 'undelivered',
    40: 'delivered',
    50: 'alert',
}
DELIVERY_STATUS = [
    ('pending', u'Pending'),
    ('notfound', u'Not Found'),
    ('transit', u'Transit'),
    ('pickup', u'Pickup'),
    ('delivered', u'Delivered'),
    ('expired', u'Expired'),
    ('undelivered', u'Undelivered'),
    ('exception', u'Exception'),
    ('alert', u'Alert')]

url_17track_detail = 'https://api.17track.net/track/v1/gettrackinfo'


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    register_17track = fields.Boolean(string='17Track Register', default=False, store=True)
    carrier_key = fields.Char('Carrier Key', related='carrier_id.carrier_key', store=True)
    track17_ffm_status = fields.Selection(DELIVERY_STATUS, string='17Track Status',
                                      readonly=True, copy=True, tracking=True)
    register_time_17track = fields.Datetime()

    def handle_job_queue_register_17track(self):
        records = self.search([('register_17track','=', False), ('tkm_ffm_status', 'in', ['pending', 'notfound'])])
        for rec in records:
            if not rec.tracking_number:
                continue
            if not rec.register_time_tracking_more:
                continue
            if rec.tkm_ffm_status in ['pending', 'notfound']:
                tx = fields.datetime.now() - rec.register_time_tracking_more
                if tx.days >= 0:
                    rec.update_tracking_order_line_17track()

    def get_headers_17track_api(self):
        headers = {
            "Content-Type": "application/json",
            "17token": self.env.user.company_id.api_key_17track}
        return headers

    def action_package_register_17track(self):
        order_line_ids = self._context.get('active_ids')
        for rec in self.search([('id', 'in', order_line_ids)]):
            if not rec.tracking_number:
                continue
            rec.update_tracking_order_line_17track()

    def request_register_17track(self):
        headers = self.get_headers_17track_api()
        body = [{
            "number": self.tracking_number,
            "carrier": self.carrier_key
        }]
        if self.env.user.company_id.url_17track_register:
            url = self.env.user.company_id.url_17track_register
        else:
            url = 'https://api.17track.net/track/v1/register'
        response = requests.post(url, headers=headers, data=json.dumps(body))
        return response

    def update_tracking_order_line_17track(self):
        response = self.request_register_17track()
        # _logger.info(API_Exception.get(response.status_code))
        if not response:
            raise UserError(_("Something went wrong register tracking to 17Track" + self.tracking_number+ '--' + self.order_id.name))
        response = response.json()
        _logger.info(f'Response sigh checking number {response}')
        data = response.get('data')
        if response.get('code') == 0 and data.get('accepted'):
            self.write({
                'register_17track': True,
                'track17_ffm_status': 'pending',
                'register_time_17track': fields.datetime.now(),
            })
        elif response.get('code') == 0 and data.get('rejected'):
            _logger.info(f'''17track message: {data.get('rejected')[0].get('error').get('message')}''')
            # update detail if tracking number is register
            package_tracking_detail = self.package_get_info_17track()
            if package_tracking_detail:
                self.write({
                    'register_17track': True,
                })
                self.update_sale_order_line_17track(self, package_tracking_detail)
        else:
            _logger.info(f'''17track message: {data.get('errors').get('message')}''')

    def package_get_info_17track(self):
        headers = self.get_headers_17track_api()
        body = [{
            "number": self.tracking_number,
        }]
        data=[]
        try:
            response = requests.post(url_17track_detail, headers=headers, data=json.dumps(body)).json()
            data = response.get("data").get("accepted")
        except Exception as e:
            _logger.info(str(e))
        if data:
            return data[0].get("track")

    def process_17track_webhook_info(self, response):
        data = response.get("data").get("track")
        _logger.info(f'webhook from 17track {response}')
        if not data:
            return False
        tracking_number = response.get("data").get("number")
        if not tracking_number:
            return False
        sale_order_line_obj = self.env['sale.order.line']
        sale_order_line_ids = sale_order_line_obj.sudo().search([('tracking_number', '=', tracking_number)])
        if not sale_order_line_ids:
            return False
        for sale_order_line_id in sale_order_line_ids:
            self.update_sale_order_line_17track(sale_order_line_id, data)

    def update_sale_order_line_17track(self, sale_order_line_id, data):
        status = track17_ffm_status.get(data.get("e")) or ''
        _logger.info(f'update sale order line id {sale_order_line_id.id} with status {status}')
        origin_info_list = data.get("z1") or ''
        destination_info_list = data.get("z2") or ''
        latest_event = data.get('z0') if data.get('z0') else {}
        sale_order_line_id.write({
            "sol_delivery_status": status,
            "track17_ffm_status": status,
            "latest_event": latest_event.get('z') or ''})
        if origin_info_list or destination_info_list:
            sale_order_line_id.tracking_info_ids.unlink()
        for info in origin_info_list:
            self.create_17track_info(info, 'origin', sale_order_line_id.id)
        for info in destination_info_list:
            self.create_17track_info(info, 'destination', sale_order_line_id.id)

    def create_17track_info(self, info, info_type, order_line_id):
        self.env['tracking.info'].sudo().create({
            'sale_order_line_id': order_line_id,
            'info_type': info_type,
            'date': info.get('a'),
            'location': info.get('c') or info.get('d'),
            'detail': info.get('z')
        })
