# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request


class ShopbaseController(http.Controller):

    def get_shopbase_webhook_store(self, webhook_store_id):
        if not webhook_store_id:
            return False
        store_webhook_id = request.env['shopbase.webhook'].sudo().search([('id', '=', webhook_store_id)])
        return store_webhook_id

    @http.route(['/shopbase/<string:type>/<string:topic>/<int:webhook_store_id>'], type='json', auth='public',
                csrf=False)
    def shopbase_webhook(self, type, topic, webhook_store_id, **kwargs):
        store_webhook_id = self.get_shopbase_webhook_store(webhook_store_id)
        data = json.loads(request.httprequest.data)
        if store_webhook_id:
            store_webhook_id._handle_shopbase_webhook(type, topic, data)
        return 'OK'

    @http.route(['/trackingmore/status'], type='json', auth='public', csrf=False)
    def trackingmore_webhook(self, **kwargs):
        response = json.loads(request.httprequest.data)
        request.env['sale.order.line'].with_delay(description='Process webhook TrackingMore!').process_trackingmore_webhook(response)
        return 'OK'

    @http.route(['/17track/status'], type='json', auth='public', csrf=False)
    def webhook_17track_info(self, **kwargs):
        response = json.loads(request.httprequest.data)
        request.env['sale.order.line'].with_delay(description='Process webhook 17Track!').process_17track_webhook_info(response)
        return 200
