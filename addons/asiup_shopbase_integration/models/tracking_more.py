# -*- coding: utf-8 -*-

from odoo import fields, models, _, api

from odoo.exceptions import ValidationError
import requests
import json
import urllib.request
import urllib.parse
from . import detect_tracking_number

# import tracking_url

DELIVERY_STATUS = [
    ('pending', u'Pending'),
    ('notfound', u'Not Found'),
    ('transit', u'Transit'),
    ('pickup', u'Pickup'),
    ('delivered', u'Delivered'),
    ('expired', u'Expired'),
    ('undelivered', u'Undelivered'),
    ('exception', u'Exception'),
    ('alert', u'Alert'),
    ('error', u'Error')]


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sol_delivery_status = fields.Selection(selection=DELIVERY_STATUS, string= 'Delivery Status')
    tkm_ffm_status = fields.Selection(selection=DELIVERY_STATUS, string='TKM status',
                                       readonly=True, copy=True, tracking=True)
    carrier_id = fields.Many2one('tracking.courier', string='Courier')
    carrier_code = fields.Char(related='carrier_id.carrier_code', store=True)
    carrier_url = fields.Char(related='carrier_id.carrier_url', string='Carrier Url', store=True)
    sale_tracking_url = fields.Char(string='Tracking Url')
    trackingmore_registed = fields.Boolean(string='Trackingmore Registed', readonly=True, copy=True, tracking=True)
    shopbase_fulfilled = fields.Boolean(string='Shopbase Fulfilled', readonly=True, copy=True, tracking=True)
    shopbase_fulfill_id = fields.Char(string='Shopbase Fulfill ID', readonly=True, copy=True, tracking=True)
    latest_event = fields.Char(string='Latest Event')
    latest_checkpoint_time = fields.Char(string='Latest Checkpoint Time')
    tracking_info_ids = fields.One2many('tracking.info', 'sale_order_line_id')
    user_tag = fields.Char(string='User Tracking')
    register_time_tracking_more = fields.Datetime()

    def handle_job_queue_register_tracking_more(self):
        domain = [('trackingmore_registed', '=', False), ('track17_ffm_status', 'in', ['pending', 'notfound'])]
        records = self.search(domain)
        for rec in records:
            if not rec.tracking_number:
                continue
            if not rec.register_time_17track:
                continue
            if rec.tkm_ffm_status in ['pending', 'notfound']:
                tx = fields.datetime.now() - rec.register_time_17track
                if tx.days >= 0:
                    rec.trackingmore_create_tracking()

    def action_package_register_tracking_more(self):
        order_line_ids = self._context.get('active_ids')
        for rec in self.search([('id', 'in', order_line_ids)]):
            if not rec.tracking_number:
                continue
            rec.trackingmore_create_tracking()

    def get_headers_trackingmore_api(self):
        headers = {
            "Content-Type": "application/json",
            "Trackingmore-Api-Key": self.env.user.company_id.trackingmore_api_key,
            'X-Requested-With': 'XMLHttpRequest'}
        return headers

    def trackingmore_detect_carriers(self):
        if self.tracking_number:
            tracking = detect_tracking_number.guess_carrier(self.tracking_number)
            carrier = tracking.carrier if tracking else self.carrier_code
            carrier_id = self.env['tracking.courier'].search([('carrier_code', '=', carrier)], limit=1)
            if not carrier_id:
                return False
            self.carrier_id = carrier_id.id
            return True

    def trackingmore_create_tracking(self):
        already_order = self.env['sale.order.line'].search([
            ("tracking_number", "=", self.tracking_number), ("trackingmore_registed", "=", True)])
        if already_order:
            self.write({'trackingmore_registed': True})
            self.with_delay(eta=30).get_trackingmore_status()
            return False
        headers = self.get_headers_trackingmore_api()
        # if self.env.user.company_id.url_trackingmore_register:
        #     url = self.env.user.company_id.url_trackingmore_register
        # else:
        url = 'https://api.trackingmore.com/v2/trackings/post'
        request_data = {
            "tracking_number": self.tracking_number,
            "carrier_code": self.carrier_code
        }
        request_data = json.dumps(request_data)
        req = urllib.request.Request(url, request_data.encode('utf-8'), headers=headers, method="POST")
        result = urllib.request.urlopen(req).read()
        result = json.loads(result.decode('utf-8'))
        if not result.get("data"):
            return False
        tkm_ffm_status = result.get("data").get("status")
        self.write({'tkm_ffm_status': tkm_ffm_status,
                    'trackingmore_registed': True, })
        self.register_time_tracking_more = fields.datetime.now()
        self.with_delay(eta=10).get_trackingmore_status()
        return True

    def get_trackingmore_status(self):
        if not self.tracking_number or not self.carrier_code:
            return False
        headers = self.get_headers_trackingmore_api()
        url = f'https://api.trackingmore.com/v2/trackings/{self.carrier_code}/{self.tracking_number}'
        req = urllib.request.Request(url, headers=headers, method="GET")
        result = urllib.request.urlopen(req).read()
        result = json.loads(result.decode('utf-8'))
        self.process_trackingmore_webhook(result)
        return True

    def get_body_fulfillment(self):
        vals = {
            "fulfillment": {
                "line_items": [{
                    "id": int(self.shopbase_line_id),
                    "quantity": self.product_uom_qty
                }],
                "tracking_number": self.tracking_number
            }
        }
        return vals

    def sync_tracking_number_to_shopbase(self):
        shopbase_url, headers = self.shopbase_store_id.get_shopbase_connect_info()
        auth = self.shopbase_store_id.get_authen()
        url = f'{shopbase_url}/admin/orders/{self.shopbase_order_id}/fulfillments.json'
        body = self.get_body_fulfillment()
        body = json.dumps(body)
        try:
            res = requests.post(url, data=body, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                shopbase_fulfill_id = content.get("fulfillment", {}).get('id')
                self.shopbase_fulfilled = True
                self.shopbase_fulfill_id = shopbase_fulfill_id
            else:
                return False
        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def get_body_update_fulfillment(self):
        vals = {
            "fulfillment": {
                "tracking_number": self.tracking_number
            }}
        return vals

    def update_tracking_number_shopbase(self):
        shopbase_url, headers = self.shopbase_store_id.get_shopbase_connect_info()
        auth = self.shopbase_store_id.get_authen()
        url = f'{shopbase_url}/admin/orders/{self.shopbase_order_id}/fulfillments/{self.shopbase_fulfill_id}.json'
        body = self.get_body_update_fulfillment()
        body = json.dumps(body)
        try:
            res = requests.put(url, data=body, auth=auth, headers=headers)
            if res.status_code == 200:
                return True
            else:
                return False
        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def process_trackingmore_webhook(self, response):
        data = response.get("data")
        if not data:
            return False
        tracking_number = data.get("tracking_number")
        carrier_code = data.get("courier_code") or data.get("carrier_code")
        status = data.get("delivery_status") or data.get("status")
        if not data.get("origin_info") and not data.get("destination_info"):
            return False
        origin_info_list = destination_info_list = False
        if data.get("origin_info"):
            origin_info_list = data.get("origin_info").get('trackinfo') or ''
        if data.get("destination_info"):
            destination_info_list = data.get("destination_info").get('trackinfo') or ''

        if not tracking_number or not carrier_code:
            return False
        sale_order_line_obj = self.env['sale.order.line']
        sale_order_line_ids = sale_order_line_obj.sudo().search([('tracking_number', '=', tracking_number)])
        if not sale_order_line_ids:
            return False
        for sale_order_line_id in sale_order_line_ids:
            sale_order_line_id.write({"tkm_ffm_status": status,
                                      "sol_delivery_status": status,
                                      "latest_event": data.get('latest_event'),
                                      "latest_checkpoint_time": data.get('latest_checkpoint_time'),
                                      "user_tag": data.get('user_tag')})
            if origin_info_list or destination_info_list:
                sale_order_line_id.tracking_info_ids.unlink()
            if origin_info_list:
                for info in origin_info_list:
                    self.create_trackingmore_info(info, 'origin', sale_order_line_id.id)
            if destination_info_list:
                for info in destination_info_list:
                    self.create_trackingmore_info(info, 'destination', sale_order_line_id.id)

    def create_trackingmore_info(self, info, info_type, order_line):
        self.env['tracking.info'].sudo().create({
            'date': info.get('checkpoint_date') or info.get('Date') or '',
            'info_type': info_type,
            'location': info.get('location') or info.get("Details") or '',
            'checkpoint_delivery_status': info.get('checkpoint_delivery_status') or info.get("checkpoint_status") or '',
            'checkpoint_delivery_substatus': info.get('checkpoint_delivery_substatus') or info.get("substatus") or '',
            'detail': info.get('tracking_detail') or info.get("StatusDescription") or '',
            'sale_order_line_id': order_line
        })


class TrackingPackageInfo(models.Model):
    _name = 'tracking.info'
    _description = 'Tracking Package Info'
    _order = 'date desc'

    sale_order_line_id = fields.Many2one('sale.order.line', string='Order Line', index=True)
    info_type = fields.Char(string='Type')
    date = fields.Datetime(string='Date Time')
    location = fields.Char(string='Location')
    detail = fields.Char(string='Detail')
    checkpoint_delivery_status = fields.Char(string='Checkpoint delivery status')
    checkpoint_delivery_substatus = fields.Char(string='Checkpoint delivery substatus')
    detail_summary = fields.Char(string='Detail', store=True, compute='_compute_detail_summary')

    @api.depends('detail')
    def _compute_detail_summary(self):
        for rec in self:
            if not rec.detail:
                rec.detail_summary = rec.detail
                continue
            end_text = '' if len(rec.detail) < 70 else '...'
            rec.detail_summary = rec.detail[:70] + end_text


class TrackingCourier(models.Model):
    _name = 'tracking.courier'
    _description = 'Tracking Courier'
    _order = 'name'

    name = fields.Char(string='Courier Name', required=True)
    carrier_code = fields.Char(string='Carrier Code', required=False)
    carrier_url = fields.Char(string='Carrier Url')
    country_id = fields.Many2one('res.country', string='Country', compute='_compute_country_id', store=True)
    country_code = fields.Char(string='Country Code')
    carrier_key = fields.Char(string='Carrier 17Track Key')

    phone = fields.Char(string='Phone')
    homepage = fields.Char(string='Homepage')
    type = fields.Char(string='Type')
    picture = fields.Char(string='Picture')

    @api.depends("country_code")
    def _compute_country_id(self):
        for rec in self:
            if not rec.country_code:
                rec.country_id = False
                continue
            country_id = rec.env['res.country'].search([('code', '=', rec.country_code)])
            if not country_id:
                rec.country_id = False
                continue
            rec.country_id = country_id.id

    def process_get_carriers_response(self, response, carrier_list):
        courier_obj = self.env['tracking.courier']
        carrier_paypal_list = self.carrier_paypal_from_csv()
        for data in response:
            code = data.get("code")
            key = self.get_carrier_key(data, carrier_list)
            carrier_paypal_code = self.get_carrier_paypal_code(data, carrier_paypal_list)
            if not code:
                continue
            already_courier = courier_obj.search([('carrier_code', '=', code)])
            vals = self.get_data_carrier(data, key, carrier_paypal_code)
            if already_courier:
                already_courier.write(vals)
                continue
            vals.update({"carrier_code": code})
            courier_obj.create(vals)

    def get_carrier_key(self, data, carrier_list):
        carrier = filter(
            lambda x: x.get('_url').lower() == data.get('homepage').lower() or x.get('_name').lower() == data.get(
                'name').lower() or x.get('_name').lower() == data.get('code').lower(), carrier_list)
        carrier = list(carrier)
        if not carrier:
            return
        else:
            return carrier[0].get('key')

    def get_data_carrier(self, data, key, carrier_paypal_code):
        return {
            "carrier_paypal_code": carrier_paypal_code,
            "carrier_key": str(key),
            "name": data.get("name"),
            "carrier_url": data.get("track_url"),
            "country_code": data.get("country_code"),
            "phone": data.get("phone"),
            "homepage": data.get("homepage"),
            "type": data.get("type"),
            "picture": data.get("picture"),
        }

    def trackingmore_get_courier(self):
        headers = {
            "Content-Type": "application/json",
            "Trackingmore-Api-Key": self.env.user.company_id.trackingmore_api_key,
            'X-Requested-With': 'XMLHttpRequest'}
        url = 'https://api.trackingmore.com/v2/carriers'

        req = urllib.request.Request(url, headers=headers, method="GET")
        result = urllib.request.urlopen(req).read()
        result = json.loads(result.decode('utf-8'))
        carrier_list = requests.get('https://www.17track.net/en/apicarrier').json()
        if not result.get("data") or not carrier_list:
            raise ValidationError(_('Cannot get carrier information!'))
        self.process_get_carriers_response(result.get("data"), carrier_list)
