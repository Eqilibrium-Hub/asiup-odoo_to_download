from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.http import request

import json
import requests
import hashlib
import hmac
import base64

SHOPBASE_WEBHOOK_TOPIC = [
    ('orders/cancelled', u'Cancelled Orders'),
    ('orders/create', u'Create Orders'),
    ('orders/fulfilled', u'Fulfilled Orders'),
    ('orders/paid', u'Paid Orders'),
    ('orders/partially_fulfilled', u'Partially Fulfilled Order'),
    ('orders/updated', u'Updated Orders'),
    ('orders/delete', u'Delete Orders'),
    ('order_transactions/create', u'Create Order Transactions'),
    ('refunds/create', u'Create Refund'),
]


class ShopbaseWebhook(models.Model):
    _name = "shopbase.webhook"
    _rec_name = 'name'
    _description = "Shopbase Webhook"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', compute='_get_name_webhook')
    webhook_id = fields.Char(string='Webhook ID', readonly=True, copy=False)
    shopbase_store_id = fields.Many2one('store.shopbase', string='Shopbase Store', required=True,
                                        tracking=True,  ondelete='cascade')
    endpoint_address = fields.Char(string='Andress', compute='get_endpoint_address')
    topic = fields.Selection(SHOPBASE_WEBHOOK_TOPIC, string='Topic', required=True, tracking=True)
    is_connect_shopbase = fields.Boolean(default=False, readonly=True, copy=False)

    _sql_constraints = [
        ('shopbase_store_topic_uniq', 'unique(shopbase_store_id, topic)', 'Shopbase store and topic must be unique !'),
    ]

    @api.depends("shopbase_store_id", "topic")
    def _get_name_webhook(self):
        for rec in self:
            if not rec.shopbase_store_id or not rec.topic:
                rec.name = _('New')
            else:
                rec.name = rec.shopbase_store_id.name + ' - ' + dict(SHOPBASE_WEBHOOK_TOPIC).get(rec.topic, '')

    @api.depends("topic")
    def get_endpoint_address(self):
        for rec in self:
            rec.endpoint_address = '/shopbase/%s' % rec.topic if rec.topic else rec.endpoint_address

    def get_base_url(self):
        self.ensure_one()
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url')

    def _verify_shopbase_signature(self):
        """
        Verify webhook with hmac, compare between X-ShopBase-Hmac-SHA256 from header of Shopbase response
        and share Share Secret key.
        """
        body = request.httprequest.data.decode("utf-8")
        shopbase_hmac = request.httprequest.headers.get('X-ShopBase-Hmac-SHA256')
        secret = self.shopbase_store_id.shared_secret
        if not shopbase_hmac or not secret:
            return False
        computed_hmac = base64.b64encode(
            hmac.new(
                key=secret.encode("utf-8"),
                msg=body.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return hmac.compare_digest(shopbase_hmac, computed_hmac)

    def get_body_webhook(self):
        address = self.get_base_url()
        body = dict()
        body['webhook'] = {
            "address": f'{address}{self.endpoint_address}/{self.id}',
            "fields": [],
            "format": "json",
            "metafield_namespaces": [],
            "topic": self.topic,
        }
        return body

    def action_create_webhook(self):
        shopbase_url, headers = self.shopbase_store_id.get_shopbase_connect_info()
        auth = self.shopbase_store_id.get_authen()
        url = '{}/admin/webhooks.json'.format(shopbase_url)
        body = self.get_body_webhook()
        body = json.dumps(body)
        try:
            res = requests.post(url, data=body, auth=auth, headers=headers)
            content = res.json()
            webhook_id = content.get('webhook', {}).get('id')
            if webhook_id:
                self.webhook_id = webhook_id
                self.is_connect_shopbase = True
            else:
                error_msg = res.content.decode('utf-8') if res.content \
                    else 'Create new webhook to shopbase fail with no result!'
                raise ValidationError(_(error_msg))

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def action_delete_webhook(self, shopbase_store_id=False, webhook_id=False, unlink=False):
        shopbase_store_id = shopbase_store_id if unlink else self.shopbase_store_id
        webhook_id = webhook_id if unlink else self.webhook_id
        shopbase_url, headers = shopbase_store_id.get_shopbase_connect_info()
        auth = shopbase_store_id.get_authen()
        url = '{}/admin/webhooks/{}.json'.format(shopbase_url, webhook_id)
        try:
            res = requests.delete(url, auth=auth, headers=headers)
            if res.status_code == 200:
                if unlink:
                    return True
                self.webhook_id = False
                self.is_connect_shopbase = False
                return True
            else:
                return False

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def unlink(self):
        for res in self:
            if res.webhook_id and res.is_connect_shopbase:
                res.action_delete_webhook(res.shopbase_store_id, res.webhook_id, unlink=True)
        return super(ShopbaseWebhook, res).unlink()

    def _handle_shopbase_webhook(self, type, topic, data):
        if not data or not self._verify_shopbase_signature():
            return False
        sale_obj = self.env['sale.order']
        refund_obj = self.env['refund.request']
        if type == 'orders' and topic == 'create':
            sale_obj.with_delay(description='Process new shopbase sale order with webhook').create_new_sale_order(
                self.shopbase_store_id, data)
        if type == 'orders' and topic == 'updated':
            sale_obj.with_delay(description='Process update shopbase sale order with webhook').update_sale_order(
                self.shopbase_store_id, data)
        if type == 'refunds' and topic == 'create':
            refund_obj.with_delay(description='Process new shopbase refund with webhook').update_refund_request(
                self.shopbase_store_id, data)
        if type == 'orders' and topic == 'cancelled':
            sale_obj.with_delay(description='Process cancel shopbase sale order with webhook').update_sale_order(
                self.shopbase_store_id, data, cancel=True)
        return True








