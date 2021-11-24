# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

import json
import requests


class ShopbasePaymentGateway(models.Model):
    _name = "woo.payment.gateway"
    _description = "Shopbase Payment Gateway"

    name = fields.Char("Payment Method", required=True)
    code = fields.Char("Payment Code", required=True,
                       help="The payment code should match Gateway ID.")
    shopbase_store_id = fields.Many2one("store.shopbase", string="Shopbase", required=False)
    shopbase_method_id = fields.Char(string='Shopbase ID', readonly=True)
    active = fields.Boolean(default=True)
    is_dead = fields.Boolean(default=False)

    _sql_constraints = [('_payment_gateway_unique_constraint', 'unique(shopbase_method_id,shopbase_store_id)',
                         "Shopbase payment gateway ID must be unique in the list")]

    def check_and_create_payment_methods(self, data, store):
        payment_methods = data.get("payment_methods")
        if not payment_methods:
            return False
        for payment_method in payment_methods:
            name = payment_method.get('title')
            code = payment_method.get('code')
            shopbase_method_id = payment_method.get('id')
            is_dead = payment_method.get("is_dead")
            active = payment_method.get("active")
            existing_payment_gateway = self.search([('shopbase_method_id', '=', shopbase_method_id),
                                                    ('shopbase_store_id', '=', store.id)]).ids
            if not name or not shopbase_method_id:
                continue
            if existing_payment_gateway:
                existing_payment_gateway.write({'active': active, 'is_dead': is_dead, 'code': code, 'name': name})
                continue
            vals = {'name': name, 'code': code, 'shopbase_store_id': store.id,
                    'active': active, 'is_dead': is_dead, 'shopbase_method_id': shopbase_method_id}
            self.create(vals)
        return True

    def shopbase_get_payment_gateway(self, store):
        """
        Get all active payment methods from shopbase by calling API.
        """
        shopbase_url, headers = store.get_shopbase_connect_info()
        auth = store.get_authen()
        url = '{}/admin/payments.json'.format(shopbase_url)
        try:
            res = requests.get(url, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                self.check_and_create_payment_methods(content, store)
            else:
                return False

        except Exception as error_msg:
            raise ValidationError(_(error_msg))
