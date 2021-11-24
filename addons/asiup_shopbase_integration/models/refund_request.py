from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import time
from datetime import datetime
import pytz
import requests
import json
from dateutil import parser

utc = pytz.utc


class RefundRequestReason(models.Model):
    _name = "refund.request.reason"

    name = fields.Char(string='Refund Reason')


class RefundRequest(models.Model):
    _name = "refund.request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'sale_order_id'
    _description = 'Refund Request'
    _order = "request_date desc"

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, tracking=True, copy=False,
                                    readonly=True, states={'confirm': [('readonly', False)]})
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(comodel_name='res.currency', string="Company Currency",
                                          related='company_id.currency_id')
    amount_total = fields.Monetary(compute='compute_amount_total', currency_field='company_currency_id',
                                   string='Amount Available', store=True)
    user_id = fields.Many2one('res.users', string='Request By', default=lambda self: self.env.user, readonly=True,
                              copy=False)
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, readonly=True, copy=False)
    note = fields.Text(compute='_compute_refund_reason', store=True)
    refund_reason = fields.Many2many('refund.request.reason', string='Refund Reason', tracking=True)
    state = fields.Selection([
        # ('draft', u'Draft'),
        ('confirm', u'Requested'),
        ('approval', u'Approval'),
        # ('done', u'Done'),
        ('reject', u'Reject')], default='confirm', string='State', tracking=True, copy=False)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', string='Customer', store=True)
    refund_amount = fields.Monetary(string='Refund Amount', currency_field='company_currency_id',
                                    tracking=True, required=False, store=True)
    type = fields.Selection([('percent', u'Refund Percent'), ('amount', u'Refund Amount')], string='Refund Type',
                            default='percent')
    refund_percent = fields.Float(string='Refund Percent')

    # Shopbase Information
    shopbase_order_id = fields.Char(related='sale_order_id.shopbase_order_id', store=True)
    shopbase_order_number = fields.Char(related='sale_order_id.shopbase_order_number', store=True)
    shopbase_store_id = fields.Many2one(related='sale_order_id.shopbase_store_id', string='Shopbase Store', store=True)
    payment_gateway_id = fields.Many2one(related='sale_order_id.payment_gateway_id', string='Shopbase Payment Gateway',
                                      store=True)
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    total_line_items_price = fields.Monetary(related='sale_order_id.total_line_items_price', string='Product Price')
    total_discounts = fields.Monetary(related='sale_order_id.total_discounts', string='Discounts')
    product_price = fields.Monetary(compute='compute_product_price', string='Product Price')
    shipping_fee = fields.Monetary(related='sale_order_id.shipping_fee', string='Shipping Fee')
    total_amount = fields.Monetary(related='sale_order_id.amount_total', string='Amount Total')
    refunded_amount = fields.Monetary(related='sale_order_id.refunded_amount', string='Refunded Amount')
    refund_shopbase_at = fields.Datetime(readonly=True, string='Shopbase Refund At')
    shopbase_refund_id = fields.Char(string='Shopbase Refund ID', readonly=True)
    ticket_link = fields.Char(string='Ticket link: ')

    def name_get(self):
        result = []
        for refund in self:
            name = 'Refund Request' + ' ' + refund.sale_order_id.name or ''
            result.append((refund.id, name))
        return result

    @api.depends("total_line_items_price", "total_discounts")
    def compute_product_price(self):
        for rec in self:
            rec.product_price = rec.total_line_items_price - rec.total_discounts

    @api.depends("refund_reason")
    def _compute_refund_reason(self):
        for rec in self:
            if not rec.refund_reason:
                rec.note = False
            else:
                rec.note = ', '.join([line.name for line in rec.refund_reason])

    @api.constrains("refund_amount", "amount_total")
    def parent_required(self):
        for record in self:
            if record.refund_amount > record.amount_total:
                raise ValidationError(_("You cannot refund more than the available amount!"))

    @api.depends('sale_order_id', 'type')
    def compute_amount_total(self):
        for rec in self:
            if rec.type == 'percent':
                rec.amount_total = rec.sale_order_id.amount_total - rec.sale_order_id.shipping_fee - rec.sale_order_id.refunded_amount
            else:
                rec.amount_total = rec.sale_order_id.amount_total - rec.sale_order_id.refunded_amount

    @api.onchange('refund_percent')
    def onchange_refund_amount(self):
        if self.type == 'percent':
            self.refund_amount = self.refund_percent * self.amount_total / 100

    # def do_confirm(self):
    #     # if all([line.refund_qty == 0.0 for line in self.refund_lines]) and not self.refund_amount:
    #     #     raise ValidationError(_('You must enter at least one refund quantity for this request!'))
    #     self.state = 'confirm'

    def do_approval(self):
        self.state = 'approval'
        if self.shopbase_order_id:
            self.sync_refund_request_to_shopbase()

    def do_reject(self):
        self.state = 'reject'

    # @api.onchange('sale_order_id')
    # def _onchange_sale_order_id(self):
    #     if self.state in ['approval', 'done']:
    #         return False
    #     if not self.sale_order_id or not self.sale_order_id.order_line:
    #         return False
    #     refund_lines_obj = self.env['refund.request.line']
    #     refund_lines = [refund_lines_obj.create({'refund_request_id': self.id, 'sale_order_line_id': line.id}).id
    #                     for line in self.sale_order_id.order_line]
    #     self.refund_lines = [(6, 0, refund_lines)]

    # def update_refund_request_line(self, data):
    #     """
    #         Map refund line from shopbase with odoo through sku and write actual refund amount on shopbase
    #     """
    #     refund_line_items = data.get("refund_line_items")
    #     if not refund_line_items:
    #         return False
    #     for item in refund_line_items:
    #         sku = item.get("line_item", {}).get("sku")
    #         quantity = item.get("quantity")
    #         subtotal = item.get("subtotal")
    #         refund_line_id = self.refund_lines.filtered(lambda t: t.product_sku == sku)
    #         if not refund_line_id:
    #             continue
    #         refund_line_id.write({
    #             'shopbase_refund_qty': quantity,
    #             'is_shopbase_refund': True})

    def _get_refund_data(self, data):
        vals = {
            # 'state': 'done',
            'shopbase_refund_id': data.get("id"),
        }
        refund_shopbase_at = data.get("processed_at")
        if refund_shopbase_at:
            refund_shopbase_at = parser.parse(refund_shopbase_at).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
            vals.update({
                'refund_shopbase_at': refund_shopbase_at
            })
        return vals

    def update_refund_request(self, store_id, data):
        """
            Update refund request with state approval in odoo from shopbase with webhook
        """
        store_id = store_id
        sale_order_id = data.get("order_id")
        if not store_id or not sale_order_id:
            return False
        refund_request = self.search(
            [('shopbase_order_id', '=', sale_order_id), ('shopbase_store_id', '=', store_id.id),
             ('state', '=', 'approval')], limit=1)
        if not refund_request:
            return False
        refund_vals = self._get_refund_data(data)
        refund_request.write(refund_vals)
        # refund_request.update_refund_request_line(data)

    def get_refund_data(self):
        """
           Get data for process sync refund request to shopbase with api.
        """
        # refund_line_items = [{
        #     "discount_amount": line.sale_order_line_id.total_discount,
        #     "line_item_id": int(line.sale_order_line_id.shopbase_order_id),
        #     "quantity": int(line.refund_qty),
        #     "raw_price": line.sale_order_line_id.price_unit,
        #     "restock_type": "return",
        # } for line in self.refund_lines if line.refund_qty > 0]

        # shipping = {"amount": self.refund_shipping}
        transactions = [{
            "amount": self.refund_amount,
            "gateway": self.payment_gateway_id.code,
            "parent_id": int(self.sale_order_id.transaction_id),
            "kind": 'refund',
        }]

        vals = {
            "refund": {
                "currency": "USD",
                "mark_as_refund": True,
                "note": self.note or '',
                "notify": True,
                # "refund_line_items": refund_line_items,
                # "restock": True if refund_line_items != [] else False,
                # "shipping": shipping if self.refund_shipping != 0.0 else {},
                "support_refund_via_api": True,
                "transactions": transactions if self.refund_amount else [],
            }}
        return vals

    def sync_refund_request_to_shopbase(self):
        """
           Sync refund request to shopbase with api.
        """
        shopbase_url, headers = self.shopbase_store_id.get_shopbase_connect_info()
        auth = self.shopbase_store_id.get_authen()
        data = self.get_refund_data()
        data = json.dumps(data)
        url = f'{shopbase_url}/admin/orders/{self.shopbase_order_id}/refunds.json'
        try:
            res = requests.post(url, data=data, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                return True
            else:
                return False

        except Exception as error_msg:
            raise ValidationError(_(error_msg))

    def unlink(self):
        for refund in self:
            if refund.state == 'approval':
                raise ValidationError(_('You cannot delete a refund request in the approval status'))
        return super().unlink()

# class RefundRequestLine(models.Model):
#     _name = "refund.request.line"
#
#     refund_request_id = fields.Many2one('refund.request', string='Refund Request')
#     sale_order_id = fields.Many2one(related='refund_request_id.sale_order_id', string='Sale Order', store=True)
#     sale_order_line_id = fields.Many2one('sale.order.line', string='Sale Order Line',
#                                          domain="['|', ('order_id', '=', False), ('order_id', '=', sale_order_id)]")
#     product_id = fields.Many2one(related='sale_order_line_id.product_id', string='Product', store=True)
#     product_sku = fields.Char(related='sale_order_line_id.product_sku', string='SKU', store=True)
#     product_uom_qty = fields.Float(related='sale_order_line_id.product_uom_qty', string='Quantity')
#     refunded_qty = fields.Float(related='sale_order_line_id.refund_qty', string='Refunded Qty', store=True)
#     price_unit = fields.Float(related='sale_order_line_id.price_unit', string='Price Unit')
#     refund_qty = fields.Float(string='Refund Qty')
#     shopbase_refund_qty = fields.Float(string='Shopbase Refund Qty', readonly=True)
#     is_shopbase_refund = fields.Boolean(readonly=True, string='Refunded on Shopbased')
#
#     @api.onchange('refund_qty')
#     def _check_qty_can_refund(self):
#         if self.refund_qty > self.product_uom_qty - self.refunded_qty:
#             raise ValidationError(_('The amount of refund has exceeded the quantity in the order!'))
