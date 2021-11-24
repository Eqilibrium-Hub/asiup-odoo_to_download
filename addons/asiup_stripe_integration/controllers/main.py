# -*- coding: utf-8 -*-
import json

from odoo import http
from odoo.http import request


class StripeController(http.Controller):

    @http.route('/dispute/stripe/webhook', type='json', auth='public', csrf=False)
    def stripe_webhook(self, **kwargs):
        data = json.loads(request.httprequest.data)
        request.env['dispute'].sudo()._handle_stripe_webhook(data)
        return 'OK'