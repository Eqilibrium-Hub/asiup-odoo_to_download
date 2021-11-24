# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from requests.auth import HTTPBasicAuth

import requests


class StoreShopbase(models.Model):
    _name = 'store.shopbase'
    _description = 'Store Shopbase'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    active = fields.Boolean(string='Active', default=False, readonly=True)
    name = fields.Char(string='Name', copy=False)
    shopbase_url = fields.Char(string='Shopbase Url', required=True, tracking=True, copy=False)
    shopbase_apikey = fields.Char(string='Shopbase Api Key', required=True, tracking=True, copy=False)
    shopbase_password = fields.Char(string='Shopbase Password', required=True, tracking=True, copy=False)
    shared_secret = fields.Char(string='Share Secret', required=True, tracking=True, copy=False)
    product_ids = fields.One2many('product.store', 'shopbase_store_id', string='Products', readonly=True)
    webhook_ids = fields.One2many('shopbase.webhook', 'shopbase_store_id', string='Webhooks', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    shopbase_id = fields.Char(string='Shopbase ID', readonly=True, copy=False)
    email = fields.Char(string='Email', readonly=True, copy=False)
    shop_owner = fields.Char(string='Shop Owner', readonly=True, copy=False)
    phone = fields.Char(string='Phone', readonly=True, copy=False)
    sales_team_id = fields.Many2one('crm.team')
    primary_domain = fields.Char(compute='_compute_primary_domain', store=True)

    # def name_get(self):
    #     name = []
    #     for rec in self:
    #         index = rec.shopbase_url.find('.onshopbase')
    #         if index:
    #             domain = rec.shopbase_url[:index] + rec.shopbase_url[index+11:]
    #             domain = domain.split('//')[-1]
    #         else:
    #             domain = rec.shopbase_url.split('//')[-1] if rec.shopbase_url.find('//') != -1 else rec.shopbase_url
    #         name.append((rec.id, domain))
    #     return name

    @api.depends("shopbase_apikey")
    def _compute_primary_domain(self):
        for rec in self:
            rec.action_check_shopbase_store()
            rec.primary_domain = rec.name

    def get_shopbase_connect_info(self):
        if not self.shopbase_url or not self.shopbase_apikey or not self.shopbase_password:
            return False, False
        headers = {
            'Content-Type': 'application/json'
        }
        return self.shopbase_url, headers

    def get_authen(self):
        res = HTTPBasicAuth(self.shopbase_apikey, self.shopbase_password)
        return res

    def update_store_shopbase_infomation(self, data):
        content = data.get('shop', {})
        state = content.get('status')
        active = True if state == 'active' else False
        sales_channel = self.shopbase_create_sales_channel(content.get('name'))
        vals = {
            'name': content.get("primary_domain"),
            'shopbase_id': content.get('id'),
            'email': content.get('email'),
            'phone': content.get('phone'),
            'shop_owner': content.get('shop_owner'),
            'active': active,
            'sales_team_id': sales_channel.id,
        }
        self.write(vals)

    def action_check_shopbase_store(self):
        shopbase_url, headers = self.get_shopbase_connect_info()
        auth = self.get_authen()
        url = '{}/admin/shop.json'.format(shopbase_url)
        try:
            res = requests.get(url, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                self.update_store_shopbase_infomation(content)
            else:
                self.active = False
        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    @api.model
    def create(self, vals):
        res = super(StoreShopbase, self).create(vals)
        res.with_delay(description='Check shopbase store is valid!').action_check_shopbase_store()
        self.env['woo.payment.gateway'].with_delay(
            description='Check shopbase payment gateway!').shopbase_get_payment_gateway(res)
        return res

    def write(self, vals):
        res = super(StoreShopbase, self).write(vals)
        for store in self:
            if 'shopbase_url' in vals or 'shopbase_apikey' in vals or 'shopbase_password' in vals:
                store.with_delay(description='Check shopbase store is valid!').action_check_shopbase_store()
                self.env['woo.payment.gateway'].with_delay(
                    description='Check shopbase payment gateway!').shopbase_get_payment_gateway(store)
        return res

    def shopbase_create_sales_channel(self,name):
        vals = {'name': name if name else '', 'use_quotations': True}
        return self.env['crm.team'].create(vals)




