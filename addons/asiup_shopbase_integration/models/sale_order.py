from odoo import api, fields, models, _
import time
import pytz
import zipcodes
import re
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError

from dateutil import parser
import requests

utc = pytz.utc

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
FFM_STATUS_EXTEND = [
    ('unfollow', u'Unfollow'),
    ('pending_export', u'Pending Export'),
    ('unexported', u'Unexported'),
    ('unfulfilled', u'Unfulfilled'),
    ('exported', u'Exported'),
    ('request_tkn', u'Request TKN'),
]
transit_status_list = ['Arrived at Sort Facility',
                       'Processing information input',
                       'Shipment transiting to next station']


class DeliveryStatusGeneral(models.Model):
    _name = "delivery.status.general"

    color = fields.Integer('Color')
    code = fields.Char('Code')
    name = fields.Char('Name')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shopbase_store_id = fields.Many2one("store.shopbase", string='Shopbase Store', copy=False, tracking=True,
                                        readonly=True, states={'draft': [('readonly', False)]})
    shopbase_order_number = fields.Char(string='Shopbase Oder Number', readonly=True, copy=False, tracking=True)
    shopbase_order_id = fields.Char(string='Shopbase Order ID', readonly=True, copy=False, tracking=True)
    order_status_url = fields.Char(string='Order Status Url', readonly=True, copy=False, tracking=True)
    payment_gateway_id = fields.Many2one('woo.payment.gateway', string='Payment Gateway', readonly=True, copy=False,
                                         tracking=True)
    transaction_authorization = fields.Char(string='Trans ID', tracking=True, readonly=True)
    transaction_id = fields.Char(string='Transaction ID', tracking=True, readonly=True)
    total_line_items_price = fields.Monetary(string='Total Price', store=True, readonly=True, tracking=True)
    total_discounts = fields.Monetary(string='Discount', store=True, readonly=True, tracking=True)
    total_discounts_negative = fields.Monetary(string='Discount', readonly=True)
    shipping_fee = fields.Monetary(string='Shipping', readonly=True, tracking=True)
    shopbase_financial_status = fields.Selection([
        ('pending', u'Pending'),
        ('authorized', u'Authorized'),
        ('refunded', u'Refunded'),
        ('partially_refunded', u'Partially refunded'),
        ('paid', u'Paid'),
        ('payment_in_process', u'Payment in process'),
        ('voided', u'Voided'),
    ], string='Shopbase Financial Status', default='pending', readonly=True, tracking=True, copy=False)

    shopbase_fulfillment_status = fields.Selection([
        ('unfulfilled', u'Unfulfilled'),
        ('partially_fulfilled', u'Partially Fulfilled'),
        ('partial', u'Partial'),
        ('fulfilled', u'Fulfilled'),
        ('processing', u'Processing'),
        ('partially_processing', u'Partially Processing'),
    ], string='Shopbase Ffm Status', default='unfulfilled', readonly=True, tracking=True, copy=False)

    order_status = fields.Selection([
        ('pending_payment', u'Pending Payment'),
        ('processing', u'Processing'),
        ('on_hold', u'On Hold'),
        ('pending', u'Pending'),
        ('cancelled', u'Cancelled'),
        ('partially_cancelled', u'Partially Cancelled'),
        ('failed', u'Failed'),
        ('delivered', u'Delivered'),
        ('reship', u'Reship'),
        ('partially_reship', u'Partially Reship')
    ], string='Order Status', readonly=True, tracking=True, copy=False)

    fulfillment_status = fields.Selection([
        ('unfollow', u'Unfollow'),
        ('pending_export', u'Pending Export'),
        ('unexported', u'Unexported'),
        ('partially_exported', u'Partially Exported'),
        ('exported', u'Exported'),
        ('error', u'Error'),
    ], string='Ffm Status', readonly=True, tracking=True, copy=False)

    payment_status = fields.Selection([
        ('pending', u'Pending'),
        ('paid', u'Paid'),
        ('partially_refunded', u'Partially Refunded'),
        ('refunded', u'Refunded'),
        ('dispute', u'Dispute'),
    ], string='Payment Status', readonly=True, tracking=True, copy=False)

    cancel_reason = fields.Text(string='Cancel Reason', tracking=True)
    cancel_at = fields.Datetime(string='Cancel At', tracking=True)
    address_error = fields.Boolean(string='Error', default=False)
    paid_at = fields.Datetime(string='Paid Date', tracking=True)
    date_paid_gmt = fields.Datetime(string='Date Paid Gmt')
    email = fields.Char(related='partner_shipping_id.email', store=True)
    phone = fields.Char(related='partner_shipping_id.phone')
    street = fields.Char(related='partner_shipping_id.street')
    street2 = fields.Char(related='partner_shipping_id.street2')
    city = fields.Char(related='partner_shipping_id.city')
    state_id = fields.Many2one(related='partner_shipping_id.state_id')
    zip = fields.Char(related='partner_shipping_id.zip')
    country_id = fields.Many2one(related='partner_shipping_id.country_id')

    refund_request_ids = fields.One2many('refund.request', 'sale_order_id', string='Refund Requests')
    refund_request_count = fields.Integer(string='Number of Refund Request', compute='_compute_refund_request')
    old_order = fields.Many2one('sale.order', string='Old Order', tracking=True)
    refunded_amount = fields.Monetary(string='Total Refunded', compute='_compute_refunded_amount', store=True)
    is_create_picking = fields.Boolean(default=True, copy=False, readonly=False)
    is_us_city = fields.Boolean(default=True)  # false if not matching zipcode
    is_us_state = fields.Boolean(default=True)  # false if not matching zipcode
    is_us_zip_code = fields.Boolean(default=True)
    is_us_order = fields.Boolean(default=True)  # false if not matching zipcode
    is_delivery_name_format = fields.Boolean(default=True)
    is_delivery_street = fields.Boolean(default=True)
    error_detail = fields.Char(string='Detail Error')
    pending_reason = fields.Many2many('pending.request.reason', string='Pending Reason', tracking=True)
    pending_request_ids = fields.One2many('pending.request', 'sale_order_id', string='Pending Request')
    last_pending_request_status = fields.Selection([
        ('draft', u'draft'),
        ('requested', u'Requested'),
        ('approved', u'Approved'),
        ('resumed', u'Resumed'),
        ('rejected', u'Rejected')], compute='_compute_last_pending_request_status',
        string='Pending last status', store=True)
    cancel_request_ids = fields.One2many('cancel.request', 'sale_order_id', string='Cancel Requests')
    last_cancel_request_status = fields.Selection([
        ('draft', u'draft'),
        ('requested', u'Requested'),
        ('approved', u'Approved'),
        ('cancelled', u'Cancelled'),
        ('rejected', u'Rejected')], compute='_compute_last_cancel_request_status',
        string='Cancel last status', store=True)
    ffm_status_before_pending = fields.Char()
    delivery_status_general = fields.Many2many('delivery.status.general', string='Delivery Status', compute='compute_delivery_status_general')
    tracking_number_general = fields.Char(string='Tracking Number', compute='compute_tracking_number_general')
    net_amount_total = fields.Monetary(string='Net Payment', store=True, compute='_compute_net_amount_total')
    related_sale_order_ids = fields.Many2many("sale.order", compute='_compute_related_sale_order_ids')
    related_sale_order_ids_2 = fields.Many2many(related='related_sale_order_ids')
    transaction_authorization_url = fields.Char(string='Transaction ID', compute='_compute_transaction_url')
    ticket_link = fields.Char(string='Ticket link: ')
    is_send_mail_create = fields.Boolean(default=False)
    problem_hide = fields.Boolean(string='Hide')

    # problem_shipping_hide = fields.Boolean(compute='compute_problem_shipping_hide')
    # problem_product_hide = fields.Boolean(compute='compute_problem_product_hide')
    #
    # @api.depends("order_line.problem_shipping_ids")
    # def compute_problem_shipping_hide(self):
    #     for rec in self:
    #         if any([line.problem_shipping_ids for line in rec.order_line]):
    #             rec.problem_shipping_hide = True
    #         else:
    #             rec.problem_shipping_hide = False
    #
    # @api.depends("order_line.problem_product_ids")
    # def compute_problem_product_hide(self):
    #     for rec in self:
    #         if any([line.problem_product_ids for line in rec.order_line]):
    #             rec.problem_product_hide = True
    #         else:
    #             rec.problem_product_hide = False

    def process_refunded_status(self):
        can_refund_amount = self.amount_total - self.shipping_fee - self.refunded_amount
        if self.refunded_amount == 0.0:
            vals = {}
        elif can_refund_amount > 0.0:
            vals = {"payment_status": "partially_refunded"}
        else:
            vals = {"payment_status": "refunded"}
        if vals:
            self.write(vals)
        return vals

    @api.depends("payment_gateway_id.code", "payment_gateway_id")
    def _compute_transaction_url(self):
        for res in self:
            if not res.payment_gateway_id:
                res.transaction_authorization_url = False
                continue
            if res.payment_gateway_id.code == 'paypal_express':
                res.transaction_authorization_url = f"https://www.paypal.com/activity/payment/{res.transaction_authorization}"
            elif res.payment_gateway_id.code == 'stripe':
                res.transaction_authorization_url = f"https://dashboard.stripe.com/payments/{res.transaction_authorization}"
            else:
                res.transaction_authorization_url = False

    @api.depends("email")
    def _compute_related_sale_order_ids(self):
        order_obj = self.env['sale.order']
        for rec in self:
            related_sale_order_ids = order_obj.search([('email', '=', rec.email), ('id', '!=', rec.id)])
            if related_sale_order_ids:
                rec.related_sale_order_ids = [(6, 0, related_sale_order_ids.ids)]
            else:
                rec.related_sale_order_ids = False

    @api.depends("amount_total", "refunded_amount")
    def _compute_net_amount_total(self):
        for rec in self:
            rec.net_amount_total = rec.amount_total - rec.refunded_amount

    @api.depends("cancel_request_ids", "cancel_request_ids.state")
    def _compute_last_cancel_request_status(self):
        for rec in self:
            if rec.cancel_request_ids:
                rec.last_cancel_request_status = rec.cancel_request_ids[0].state
            else:
                rec.last_cancel_request_status = False

    @api.depends("pending_request_ids", "pending_request_ids.state")
    def _compute_last_pending_request_status(self):
        for rec in self:
            if rec.pending_request_ids:
                rec.last_pending_request_status = rec.pending_request_ids[0].state
            else:
                rec.last_pending_request_status = False

    @api.depends('order_line.sol_delivery_status')
    def compute_delivery_status_general(self):
        delivery_status_general_obj = self.env['delivery.status.general']
        for rec in self:
            line_dsg = [line.sol_delivery_status for line in rec.order_line if
                        line.tracking_number and line.sol_fulfillment_status and not line.is_extra_line]
            if not line_dsg:
                rec.delivery_status_general = False
                continue
            dsg_ids = delivery_status_general_obj.search([('code', 'in', line_dsg)])
            rec.delivery_status_general = [(6, 0, dsg_ids.ids)]

    @api.depends('order_line.tracking_number')
    def compute_tracking_number_general(self):
        for rec in self:
            tracking_number = [line.tracking_number for line in rec.order_line if line.tracking_number and not line.is_extra_line]
            if not tracking_number:
                rec.tracking_number_general = False
            else:
                rec.tracking_number_general = ' '.join(tracking_number)

    @api.depends('refund_request_ids', 'refund_request_ids.refund_amount', 'refund_request_ids.state')
    def _compute_refunded_amount(self):
        for rec in self:
            rec.refunded_amount = sum([line.refund_amount for line in rec.refund_request_ids if line.state == 'approval'])

    def _prepare_confirmation_values(self):
        return {
            'state': 'sale',
        }

    # override compute sale amount
    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
            if amount_untaxed + amount_tax:
                amount_total = amount_untaxed + amount_tax
                max_amount = self.env.user.company_id.max_amount
                if not max_amount:
                    continue
                if amount_total >= max_amount:
                    if order.order_status in ['processing', 'pending']:
                        order.set_status_max_amount_total(max_amount)

    def confirm_address_edit_status(self):
        self.write({
            'order_status': 'processing',
            'fulfillment_status': 'unexported',
        })
        if 'error' in self.pending_reason.mapped('code'):
            reason_id = self.pending_reason.search([('code', '=', 'error')], limit=1)
            self.write({
                'pending_reason': [(3, reason_id.id)]
            })

    def action_confirm_shipping_address(self):
        if self.address_error is True:
            self.write({
                'is_us_city': True,
                'is_us_state': True,
                'is_us_zip_code': True,
                'is_us_order': True,
                'is_delivery_name_format': True,
                'address_error': False,
                'error_detail': False
            })
            self.confirm_address_edit_status()
            for rec in self.order_line:
                rec.confirm_address_edit_status()
            exist_extend = self.env['asiup.extend.address.shipping'].search(
                [('country_id', '=', self.partner_shipping_id.country_id.id), ('zip', '=', self.partner_shipping_id.zip),
                 ('city', '=', self.partner_shipping_id.city), ('state_id', '=', self.partner_shipping_id.state_id.id)])
            if not exist_extend:
                self.env['asiup.extend.address.shipping'].create({
                    'country_id': self.partner_shipping_id.country_id.id,
                    'zip': self.partner_shipping_id.zip,
                    'city': self.partner_shipping_id.city,
                    'state_id': self.partner_shipping_id.state_id.id,
                })

    def set_status_order_pending(self, reason_ids=''):
        if not reason_ids:
            self.write({
                'order_status': 'pending',
                'fulfillment_status': 'pending_export'
            })
            return True
        self.write({
            'pending_reason': [(6, 0, reason_ids)],
            'order_status': 'pending',
            'fulfillment_status': 'pending_export'
        })
        return True

    def set_status_order_by_state(self, code):
        self.set_status_order_pending(self.get_pending_reason(code.lower(), code))
        for line in self.order_line.filtered(lambda r: r.is_extra_line is False):
            line.set_status_order_line_pending(self.get_pending_reason(code.lower(), code))

    def set_status_order_duplicate(self):
        if self.fulfillment_status in ['unexported', 'pending']:
            self.set_status_order_pending(self.get_pending_reason('duplicate_sol', 'Duplicate Sale Order Line'))
            # self.set_status_order_line_pending(self.get_pending_reason('duplicate_sol', 'Duplicate Sale Order Line'))

    def set_status_address_error(self):
        self.set_status_order_pending(self.get_pending_reason('error', 'Address Error'))
        for line in self.order_line.filtered(lambda r: r.is_extra_line is False):
            line.set_status_order_line_pending(self.get_pending_reason('error', 'Address Error'))

    def set_status_max_amount_total(self, max_amount):
        self.set_status_order_pending(self.get_pending_reason(f'amount_{max_amount}', f'Total > {max_amount}'))
        for line in self.order_line.filtered(lambda r: r.is_extra_line is False):
            line.set_status_order_line_pending(self.get_pending_reason(f'amount_{max_amount}', f'Total > {max_amount}'))

    def get_pending_reason(self, reason_code, reason_name):
        # return list pending reason id
        reason_id = self.env['pending.request.reason'].search([('code', '=', reason_code)], limit=1)
        if not reason_id:
            reason_id = self.pending_reason.create({
                'code': reason_code,
                'name': reason_name
            })
        if self.pending_reason:
            if reason_id in self.pending_reason.ids:
                return self.pending_reason.ids
            return self.pending_reason.ids + reason_id.ids
        return reason_id.ids

    @api.depends('refund_request_ids')
    def _compute_refund_request(self):
        for refund in self:
            refund.refund_request_count = len(refund.refund_request_ids)

    def action_view_refund_request(self):
        self.ensure_one()
        refund_request_ids = self.refund_request_ids.ids
        action = {
            'name': _('Refund Request of %s', self.name),
            'res_model': 'refund.request',
            'type': 'ir.actions.act_window',
            'context': {'default_sale_order_id': self.id},
            'domain': [('id', 'in', refund_request_ids)],
            'view_mode': 'tree,form',
        }
        return action

    def create_pending_request(self):
        for rec in self.pending_request_ids:
            if rec.state == 'requested':
                raise ValidationError(_('order already exists pending request pending approval!'))
        action = {
            'res_model': 'pending.request',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('asiup_shopbase_integration.pending_request_form_view').id,
            'context': {'default_sale_order_id': self.id},
            'target': 'new'
        }
        return action

    def create_cancel_request(self):
        for rec in self.pending_request_ids:
            if rec.state == 'requested':
                raise ValidationError(_('order already exists cancel request pending approval!'))
        action = {
            'res_model': 'cancel.request',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('asiup_shopbase_integration.cancel_request_form_view').id,
            'context': {'default_sale_order_id': self.id},
            'target': 'new'
        }
        return action

    def action_confirm_multi_shipping_address(self):
        for rec in self.search([('id', 'in', self._context.get('active_ids'))]):
            if rec.address_error:
                rec.action_confirm_shipping_address()

    def action_fail_sale_order(self):
        self.order_status = 'failed'

    def action_processing_multi_sale_order(self):
        for rec in self:
            if rec.order_status not in ['on_hold', 'pending_payment'] and rec.fulfillment_status != 'pending_export':
                continue
            rec.action_processing_sale_order()

    def action_processing_sale_order(self):
        if self.order_status not in ['on_hold', 'pending_payment'] and self.fulfillment_status != 'pending_export':
            return False

        self.order_status = 'processing'
        self.fulfillment_status = 'unexported'
        return True

    def action_pending_multi_sale_order(self):
        for rec in self.search([('id', 'in', self._context.get('active_ids'))]):
            if rec.fulfillment_status != 'unexported':
                continue
            rec.action_pending_sale_order()

    def confirm_action_pending_so(self):
        view = self.env.ref('asiup_shopbase_integration.order_message_wizard')
        context = dict(self._context or {})
        context.update({'default_sale_order_id': self.id,
                        'default_type_message': 'pending_order'})
        dic_msg = "Pending Reason"
        context['message'] = dic_msg

        return {
            'name': 'Confirm Pending Order',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'order.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def action_pending_sale_order(self):
        if self.fulfillment_status != 'unexported':
            raise UserError(_('You can only pending SO with state "Unexported"'))

        self.ffm_status_before_pending = self.fulfillment_status
        self.order_status = 'pending'
        self.fulfillment_status = 'pending_export'
        for rec in self.order_line:
            rec.action_pending_order_line()

    def action_resume_multi_sale_order(self):
        for rec in self.search([('id', 'in', self._context.get('active_ids'))]):
            rec.action_resume_sale_order()

    def action_resume_sale_order(self):
        if self.order_status in ['on_hold', 'pending_payment'] and not self.is_send_mail_create:
            self.action_send_mail_order('mail_template_order_create')
            self.send_message_sms(self, self.partner_shipping_id, 'new_sale_order')
            self.is_send_mail_create = True

        self.order_status = 'processing'
        self.fulfillment_status = 'unexported'
        for line in self.order_line:
            line.action_processing_sale_order_line()
        pending_request = self.pending_request_ids.filtered(lambda t: t.state == 'approved')
        if pending_request:
            pending_request.write({'state': 'resumed'})
        return True

    def action_cancel_multi_sale_order(self):
        for rec in self.search([('id', 'in', self._context.get('active_ids'))]):
            rec.action_cancel_sale_order()

    def action_cancel_sale_order(self):
        if self.fulfillment_status not in ['unexported', 'pending_export']:
            raise UserError(_('SO fulfillment status not in Unexported or Pending'))
        self.cancel_from_cancel_request()

    def confirm_action_cancel_so(self):
        view = self.env.ref('asiup_shopbase_integration.order_message_wizard')
        context = dict(self._context or {})
        context.update({'default_sale_order_id': self.id,
                        'default_type_message': 'cancel_order'})
        dic_msg = "Do you really want to cancel this order?"
        context['message'] = dic_msg
        return {
            'name': 'Confirm Cancel Order',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'order.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def pending_so_from_pending_request(self):
        self.order_status = 'pending'
        for line in self.order_line:
            line.sol_status = 'pending'
        return True

    def cancel_from_cancel_request(self, status_invoice=False):
        self.order_status = 'cancelled'
        self.fulfillment_status = 'unfollow'
        for line in self.order_line:
            line.sol_status = 'cancelled'
            line.sol_fulfillment_status = 'unfollow'
            line.sol_invoice_status = status_invoice
        return True

    def action_view_order_web(self):
        return {
            "url": self.order_status_url,
            "type": "ir.actions.act_url"
        }

    def convert_order_date(self, order_response):
        """ This method is used to convert the order date in UTC and formate("%Y-%m-%d %H:%M:%S").
            :param order_response: Order response
        """
        if order_response.get("created_at", False):
            order_date = order_response.get("created_at", False)
            date_order_gmt = datetime.strptime(order_date.replace("T", " "), '%Y-%m-%d %H:%M:%S+00:00') - timedelta(hours=15)
            date_order = date_order_gmt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            date_order = datetime.strptime(time.strftime("%Y-%m-%d %H:%M:%S"), '%Y-%m-%d %H:%M:%S') - timedelta(hours=15)
            date_order = date_order.strftime("%Y-%m-%d %H:%M:%S")

        return date_order

    def get_transaction_authorization_from_response(self, content):
        transactions = content.get("transactions")
        if not transactions:
            return False
        transaction = [(trans.get("id"), trans.get("authorization"), trans.get("payment_method_id")) for trans in
                       transactions if trans.get("kind") and trans.get("kind") == 'capture']
        transaction_id = transaction[0][0] if transaction[0] else False
        transaction_authorization = transaction[0][1] if transaction[0] else False
        payment_method = transaction[0][2] if transaction[0] else False
        payment_method_id = False
        if payment_method:
            payment_method_id = self.env['woo.payment.gateway'].search(
                [('shopbase_method_id', '=', payment_method)])

        return transaction_id, transaction_authorization, payment_method_id

    def get_transaction_authorization_from_shopbase(self, store_id, shopbase_order_id):
        """
            Get transaction id from shopbase and updat in sale order vals
        """
        shopbase_url, headers = store_id.get_shopbase_connect_info()
        auth = store_id.get_authen()
        url = f'{shopbase_url}/admin/orders/{shopbase_order_id}/transactions.json'
        try:
            res = requests.get(url, auth=auth, headers=headers)
            if res.status_code == 200:
                content = res.json()
                transaction_id, transaction_authorization, payment_method_id = self.get_transaction_authorization_from_response(
                    content)
                return transaction_id, transaction_authorization, payment_method_id
            else:
                return False, False, False
        except Exception:
            return False, False, False

    def prepare_order_vals_from_order_response(self, order_response, store_id):
        """
        This method is used to prepare vals from the order response.
        """
        shipping = order_response.get("shipping_lines")
        shipping_fee = sum([line.get("price", 0.0) for line in shipping])
        shopbase_order_id = order_response.get("id")
        transaction_id, transaction_authorization, payment_method_id = self.get_transaction_authorization_from_shopbase(
            store_id, shopbase_order_id)
        order_vals = {
            "shopbase_order_id": shopbase_order_id,
            "shopbase_order_number": order_response.get("order_number"),
            "shopbase_store_id": store_id.id,
            "shopbase_financial_status": order_response.get("financial_status") or "pending",
            "shopbase_fulfillment_status": order_response.get("fulfillment_status") or "unfulfilled",
            "name": order_response.get("name"),
            "order_status_url": order_response.get("order_status_url"),
            "transaction_authorization": transaction_authorization,
            "transaction_id": transaction_id,
            "total_discounts": order_response.get("total_discounts"),
            "total_discounts_negative": 0 - order_response.get("total_discounts"),
            "shipping_fee": shipping_fee,
            "total_line_items_price": order_response.get("total_line_items_price"),
            "note": order_response.get("note"),
            "payment_gateway_id": payment_method_id.id if payment_method_id else False,
            "is_create_picking": False,
        }
        return order_vals

    def prepare_shopbase_order_vals(self, data, store_id, partner, shipping_address, invoice_address):
        """
        This method used to Prepare a order vals.
        @param : self, data, store_id, partner, shipping_address,invoice_address
        @return: order_vals
        """
        date_order = self.convert_order_date(order_response=data)
        ordervals = {
            "company_id": store_id.company_id.id if store_id.company_id else False,
            "partner_id": partner.ids[0],
            "partner_invoice_id": invoice_address.ids[0],
            "partner_shipping_id": shipping_address.ids[0],
            "date_order": date_order,
            "team_id": store_id.sales_team_id.id if store_id.sales_team_id else False,
            "state": "sale",
        }
        order_response_vals = self.prepare_order_vals_from_order_response(data, store_id)
        ordervals.update(order_response_vals)
        return ordervals

    def search_shopbase_product_for_order_line(self, line, store_id):
        """This method used to search shopbase product for order line.
            @param : self, line
            @return: shopbase_product
        """
        # product_obj = self.env["product.product"]
        # shopbase_product = product_obj.search([("product_sku", "=", line.get("sku"))])
        variant_store_obj = self.env["product.variant.store"]
        shopbase_variant_store_id = variant_store_obj.search([
            ("variant_sku", "=", line.get("sku")), ("shopbase_store_id", "=", store_id.id)])
        if not shopbase_variant_store_id:
            return False
        shopbase_product = shopbase_variant_store_id.product_variant_id
        if shopbase_product:
            return shopbase_product
        return False

    def prepare_vals_for_sale_order_line(self, line, store_id):
        """ This method is used to prepare a vals to create a sale order line.
        """
        product = self.search_shopbase_product_for_order_line(line, store_id)
        if not product:
            self.env['product.store'].sync_product_from_a_shopbase(store_id)
            product = self.search_shopbase_product_for_order_line(line, store_id)
            if not product:
                return False
        uom_id = product and product.uom_id and product.uom_id.id or False
        line_vals = {
            "product_id": product and product.ids[0] or False,
            "order_id": self.id,
            "company_id": self.company_id.id,
            "product_uom": uom_id,
            "name": line.get('name'),
            "price_unit": line.get('price'),
            "order_qty": line.get('quantity'),
            "total_discount": line.get('total_discount'),
            "product_sku": line.get('sku'),
        }
        return line_vals

    def create_shopbase_order_lines(self, lines, store_id):
        sale_order_line_obj = self.env["sale.order.line"]
        for line in lines:
            line_vals = self.prepare_vals_for_sale_order_line(line, store_id)
            if not line_vals:
                continue
            order_line_vals = sale_order_line_obj.create_sale_order_line(line_vals)
            order_line_vals.update({
                "shopbase_line_id": line.get("id"),
            })
            sale_order_line_obj.create(order_line_vals)

    def find_or_create_shopbase_delivery_carrier(self, data):
        delivery_carrier_obj = self.env["delivery.carrier"]
        shopbase_code = data.get("code")
        name = data.get("title")
        carrier = delivery_carrier_obj.search([("shopbase_code", "=", shopbase_code)], limit=1)
        if not carrier:
            carrier = delivery_carrier_obj.search([("name", "=", name)], limit=1)
        if not carrier:
            carrier = delivery_carrier_obj.search(["|", ("name", "ilike", name),
                                                   ("shopbase_code", "ilike", shopbase_code)], limit=1)
        if not carrier:
            shipping_product = self.env['product.product'].create({
                'name': name, 'type': 'service', 'invoice_policy': 'order', 'description': 'Shipping Fees',
                'default_code': shopbase_code, 'standard_price': data.get("price"), 'list_price': data.get("price")})

            carrier = delivery_carrier_obj.create({"name": name, "shopbase_code": shopbase_code,
                                                   "fixed_price": data.get("price"),
                                                   "product_id": shipping_product.id})
        return carrier

    def create_shopbase_shipping_line(self, data):
        shipping_lines = data.get("shipping_lines")
        if not shipping_lines:
            return False
        for shipping_line in shipping_lines:
            carrier = self.find_or_create_shopbase_delivery_carrier(shipping_line)
            shipping_product = carrier.product_id
            self.write({"carrier_id": carrier.id})
            line_vals = {
                "name": shipping_product.name,
                "product_id": shipping_product.id,
                "product_uom": shipping_product.uom_id.id if shipping_product.uom_id else False,
                "order_id": self.id,
                "product_uom_qty": 1,
                'is_extra_line': True,
                "price_unit": shipping_product.standard_price,
            }
            self.env['sale.order.line'].create(line_vals)
        return True

    def create_sale_order_from_shopbase(self, data, store_id, partner, shipping_address, invoice_address):
        order_vals = self.prepare_shopbase_order_vals(data, store_id, partner, shipping_address, invoice_address)
        order = self.create(order_vals)
        lines = data.get("line_items")
        order.create_shopbase_order_lines(lines, store_id)
        order.create_shopbase_shipping_line(data)

    def create_new_sale_order(self, store_id, data):
        partner, delivery_address, invoice_address = self.env['res.partner'].create_or_update_customer(data, store_id)
        if not partner:
            return False
        self.create_sale_order_from_shopbase(data, store_id, partner, delivery_address, invoice_address)

    def check_delivery_address_fraud(self):
        address_error = False
        exist_extend = self.env['asiup.extend.address.shipping'].search(
            [('country_id', '=', self.partner_shipping_id.country_id.id), ('zip', '=', self.partner_shipping_id.zip),
             ('city', '=', self.partner_shipping_id.city), ('state_id', '=', self.partner_shipping_id.state_id.id)])
        if exist_extend:
            return address_error

        delivery_address = self.partner_shipping_id
        if not delivery_address.id:
            self.address_error = True
            return address_error

        try:
            zipcode_detail = zipcodes.matching(delivery_address.zip)[0]
            self.is_us_zip_code = True
        except Exception:
            self.is_us_zip_code = False
            address_error = True
            return address_error

        if not zipcode_detail:
            self.is_us_zip_code = False
            address_error = True
            return address_error

        if delivery_address.city:
            zipcode_city = []
            zipcode_city.append(self.process_delivery_city(zipcode_detail.get('city')))
            if zipcode_detail.get('acceptable_cities'):
                zipcode_city = zipcode_city + [self.process_delivery_city(city) for city in zipcode_detail.get('acceptable_cities')]
            if self.process_delivery_city(delivery_address.city) not in zipcode_city:
                self.is_us_city = False
                address_error = True
            else:
                self.is_us_city = True
        else:
            address_error = True

        if delivery_address.state_id.country_id.code != 'US':
            self.is_us_state = False
            address_error = True
        else:
            self.is_us_state = True

        if delivery_address.country_id.code != 'US':
            address_error = True
            self.is_us_order = False
        else:
            self.is_us_order = True

        if not self.check_delivery_street(delivery_address.street):
            self.is_delivery_street = False
            address_error = True

        self.address_error = address_error
        return address_error

    def check_delivery_street(self, street):
        is_number = re.compile('[\d+]')
        is_string = re.compile('[a-zA-Z]')
        if is_number.search(street) and is_string.search(street):
            return True
        return False

    def process_delivery_city(self, city):
        city = city.lower().replace(' ', '')
        if city.find('city') != -1:
            index = city.find('city')
            city = city[:index] + city[index + 4:]
        city = ''.join(char for char in city if char.isalnum())
        return city

    # Update sale order from shopbase with webhook
    def prepare_shopbase_update_order_vals(self, data):
        cancel_at = data.get("cancel_at")
        if cancel_at:
            cancel_at = datetime.strptime(cancel_at.replace("T", " "), '%Y-%m-%d %H:%M:%S+00:00') - timedelta(hours=15)
            cancel_at = cancel_at.strftime('%Y-%m-%d %H:%M:%S')
        else:
            cancel_at = datetime.strptime(time.strftime("%Y-%m-%d %H:%M:%S"), '%Y-%m-%d %H:%M:%S') - timedelta(
                hours=15)
            cancel_at = cancel_at.strftime("%Y-%m-%d %H:%M:%S")
        order_vals = {
            "shopbase_financial_status": data.get("financial_status") or "pending",
            "shopbase_fulfillment_status": data.get("fulfillment_status") or "unfulfilled",
            "cancel_reason": data.get("cancel_reason"),
            "cancel_at": cancel_at,
        }
        return order_vals

    def cancel_sale_order(self):
        self.action_cancel()
        self.cancel_in_woo()
        # for line in self.order_line:
        #     line.shopbase_fulfillment_status = 'canceled'
        return True

    def update_sale_order(self, store_id, data, cancel=False):
        order_vals = self.prepare_shopbase_update_order_vals(data)
        if not self.transaction_authorization and self.shopbase_order_id:
            transaction_id, transaction_authorization, payment_method_id = self.get_transaction_authorization_from_shopbase(
                store_id, self.shopbase_order_id)
            order_vals.update(
                {'transaction_authorization': transaction_authorization, 'transaction_id': transaction_id})
            if payment_method_id:
                order_vals.update({'payment_gateway_id': payment_method_id.id})
        shopbase_order_number = data.get("order_number")
        old_order = self.env['sale.order'].search([('shopbase_order_number', '=', shopbase_order_number),
                                                   ('shopbase_store_id', '=', store_id.id)])
        if not old_order:
            return False
        old_order.write(order_vals)
        if cancel:
            old_order.cancel_sale_order()
        if data.get('note'):
            old_order.update_transaction_from_cancel_order(old_order, data.get('note'))
        return True

    def update_transaction_from_cancel_order(self, old_order, note):
        for st in note.split():
            if st.find("###") == -1:
                continue
            shopbase_order_id = st.strip().split('/')[-1]
            if not shopbase_order_id:
                continue
            cancel_order = self.env['sale.order'].search([('shopbase_order_id', '=', shopbase_order_id)])
            if not cancel_order:
                continue
            if cancel_order.state != 'cancel':
                cancel_order.state = 'cancel'
            old_order.transaction_authorization = cancel_order.transaction_authorization \
                if cancel_order.transaction_authorization else ''
            old_order.old_order = cancel_order.id

    def compute_delivery_address_error(self):
        for res in self:
            if res.partner_shipping_id:
                address_error = res.check_delivery_address_fraud()
                if address_error:
                    res.set_status_address_error()
                    res.order_line._compute_detail_error_summary()
                if res.partner_shipping_id.state_id.code in ['AK', 'HI', 'PR', 'VI', 'APO', 'APE']:
                    res.set_status_order_by_state(res.partner_shipping_id.state_id.code)
            else:
                res.address_error = False
                # res.set_status_order_by_state('No Shipping Address')

    @api.model
    def create(self, vals_list):
        res = super(SaleOrder, self).create(vals_list)
        return res

    def unlink(self):
        for rec in self:
            rec.state = 'cancel'
        return super(SaleOrder, self).unlink()

    @staticmethod
    def send_message_sms(obj, partner_id=False, condition=''):
        if not (condition):
            return
        sms_template_objs = obj.env["wk.sms.template"].search(
            [('condition', '=', condition), ('globally_access', '=', False)])
        if not sms_template_objs:
            return False
        for sms_template_obj in sms_template_objs:
            mobile = sms_template_obj._get_partner_mobile(partner_id)
            if mobile:
                sms_template_obj.send_sms_using_template(
                    mobile, sms_template_obj, obj=obj)

    def processing_new_order_in_odoo(self):
        if self.order_status in ['processing', 'pending'] and not self.is_send_mail_create:
            self.action_send_mail_order('mail_template_order_create')
            self.send_message_sms(self, self.partner_shipping_id, 'new_sale_order')
            self.is_send_mail_create = True

    def processing_new_order_in_odoo_test(self):
        self.action_send_mail_order('mail_template_order_create')
        self.send_message_sms(self, self.partner_shipping_id, 'new_sale_order')


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ['sale.order.line', 'mail.thread', 'mail.activity.mixin']

    order_id = fields.Many2one('sale.order', string='Order Number', tracking=True)
    product_label = fields.Char(related="product_tmpl_id.product_label", store=True)
    ffm_date = fields.Datetime(string='FFM Date')
    latency_ffm_date = fields.Char(string='Latency FFM Date', compute='compute_latency_date', store=True)
    latency_ffm_date_num = fields.Float(string='Latency FFM Date', compute='compute_latency_date', store=True)
    latency_paid_date = fields.Char(string='Latency Paid Date', compute='compute_latency_date', store=True)
    latency_paid_date_num = fields.Float(string='Latency Paid Date', compute='compute_latency_date', store=True)
    product_uom_qty = fields.Float(string='Quantity', digits=(12, 0), required=True, default=1.0)
    shopbase_store_id = fields.Many2one(related='order_id.shopbase_store_id', string='Shopbase Store', store=True,
                                        tracking=True)
    shopbase_order_number = fields.Char(related='order_id.shopbase_order_number', string='Shopbase Order Number',
                                        store=True, tracking=True)
    shopbase_order_id = fields.Char(related='order_id.shopbase_order_id', string='Shopbase Order ID', store=True)
    shopbase_financial_status = fields.Selection(related='order_id.shopbase_financial_status', store=True)
    shopbase_line_id = fields.Char(string="shopbase Line", readonly=True, copy=False, tracking=True)

    date_order = fields.Datetime(related="order_id.date_order", string="Created Date", readonly=True, store=True,
                                 tracking=True)
    partner_shipping_id = fields.Many2one(related="order_id.partner_shipping_id", string="Delivery Address",
                                          readonly=True, store=True, tracking=True)
    partner_invoice_id = fields.Many2one(related="order_id.partner_invoice_id", string="Invoice Address",
                                         readonly=True, store=True, tracking=True)
    tracking_number = fields.Char(string=u'TKN', tracking=True, index=True)
    total_discount = fields.Float(string='Discount', digits='Discount', default=0.0, tracking=True)
    product_sku = fields.Char(string='SKU', tracking=True, readonly=True)
    product_url = fields.Text(string='Url')
    product_name = fields.Char(related='product_id.name')
    sol_status = fields.Selection([
        ('processing', u'Processing'),
        ('on_hold', u'On-Hold'),
        ('pending', u'Pending'),
        ('pending_payment', u'Pending Payment'),
        ('cancelled', u'Cancelled'),
        ('failed', u'Failed'),
        ('delivered', u'Delivered'),
        ('reship', u'Reship'),
    ], string='Order Status', tracking=True, readonly=True)

    sol_payment_status = fields.Selection([
        ('paid', u'Paid'),
        ('pending', u'Pending'),
        ('refunded', u'Refunded'),
    ], string='Payment Status', tracking=True, readonly=True)

    paid_at = fields.Datetime(string='Paid Date', related="order_id.paid_at")
    sol_fulfillment_status = fields.Selection(selection=FFM_STATUS_EXTEND,
                                              string='Ffm Status', tracking=True, readonly=False)
    # refund_lines = fields.One2many('refund.request.line', 'sale_order_line_id', string='Refund Lines')
    # refund_qty = fields.Float(string='Refund Qty', compute='_compute_refunded_qty')
    is_product_set = fields.Boolean(related='product_id.is_product_set', string='Is Set')
    address_error = fields.Boolean(related="order_id.address_error", string='Error', store=True)
    email = fields.Char(related='partner_shipping_id.email')
    phone = fields.Char(related='partner_shipping_id.phone')
    street = fields.Char(related='partner_shipping_id.street')
    street2 = fields.Char(related='partner_shipping_id.street2')
    city = fields.Char(related='partner_shipping_id.city')
    is_us_city = fields.Boolean(related='order_id.is_us_city', store=True,
                                default=True)  # false if not matching zipcode
    state_id = fields.Many2one('res.country.state', related='partner_shipping_id.state_id')
    is_us_state = fields.Boolean(related='order_id.is_us_state', store=True,
                                 default=True)  # false if not matching zipcode
    zip = fields.Char(related='partner_shipping_id.zip')
    is_us_zip_code = fields.Boolean(related='order_id.is_us_zip_code', store=True, default=True)
    country_id = fields.Many2one('res.country', related='partner_shipping_id.country_id')
    is_us_order = fields.Boolean(related='order_id.is_us_order', store=True,
                                 default=True)  # false if not matching zipcode
    is_delivery_name_format = fields.Boolean(related='order_id.is_delivery_name_format', store=True, default=True)
    is_delivery_street = fields.Boolean(related='order_id.is_delivery_street', store=True, default=True)
    delivery_name = fields.Char(related='partner_shipping_id.name')
    is_extra_line = fields.Boolean(default=False, string='Extra Line', readonly=True)
    error_detail = fields.Char(string='Detail Error', compute='_compute_detail_error_summary')
    pending_reason = fields.Many2many('pending.request.reason', string='Pending Reason', tracking=True)
    sol_invoice_status = fields.Boolean()
    processing_time = fields.Char(string='Processing Time', compute='compute_processing_time', store=False)
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id', store=True)
    claim_reason = fields.Many2many('asiup.claim.reason', string='Claim Reason', tracking=True)
    note_ffm = fields.Text(string='Note FFM', tracking=True)
    note_cs = fields.Text(string='Note CS', tracking=True)
    problem_shipping_ids = fields.Many2many('asiup.product.shipping.problem', 'problem_shipping_sale_order_line_rel', string='Problem Shipping')
    problem_product_ids = fields.Many2many('asiup.product.shipping.problem', 'problem_product_sale_order_line_rel', string='Problem Product')
    is_line_send_mail_tracking = fields.Boolean(default=False)
    attribute_variant_lst = fields.Char(string='String', related='product_id.attribute_variant_lst')
    product_cost = fields.Float(string='Cost', store=True)
    quote_status = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm')], string='Quote Status')
    supplier = fields.Many2one('res.partner', string='Supplier', tracking=True)
    qty_per_sku = fields.Integer(string='Qty Per SKU', related='product_id.qty_per_sku')

    def update_product_url(self):
        if not self.order_id:
            return False
        if not self.order_id.woo_instance_id:
            return False
        if not self.product_id:
            return False
        domain = [("woo_instance_id", "=", self.order_id.woo_instance_id.id), ("product_id", "=", self.product_id.id)]
        woo_product_id = self.env['woo.product.product.ept'].search(domain, limit=1)
        if not woo_product_id:
            return False
        if not self.product_url:
            self.product_url = woo_product_id.product_url
        if not self.product_sku:
            self.product_sku = woo_product_id.default_code

    @api.depends('tracking_info_ids.detail_summary')
    def compute_processing_time(self):
        for rec in self:
            if not rec.ffm_date or not rec.tracking_info_ids:
                rec.processing_time = False
                continue
            for transit_status in transit_status_list:
                info = rec.tracking_info_ids.search([('detail', 'ilike', transit_status), ('sale_order_line_id', '=', rec.id)], limit=1)
                if not info:
                    rec.processing_time = False
                    continue
                else:
                    rec.processing_time = self.display_timedelta_latency(info.date - rec.ffm_date)
                    break

    @api.depends('is_us_city', 'is_us_state', 'is_us_zip_code', 'is_us_order', 'is_delivery_street')
    def _compute_detail_error_summary(self):
        for rec in self:
            detail_error = rec.get_detail_error_summary()
            if len(detail_error) >= 19:
                detail_error = detail_error[:15] + '...'
            rec.error_detail = detail_error
            rec.order_id.error_detail = detail_error

    @api.depends('ffm_date', 'paid_at', 'tracking_info_ids', 'tracking_info_ids.date')
    def compute_latency_date(self):
        for rec in self:
            if not rec.tracking_info_ids.mapped('date'):
                rec.latency_paid_date, rec.latency_ffm_date = False, False
                continue
            late_tracking_info_date = max(rec.tracking_info_ids.mapped('date'))
            if rec.ffm_date:
                rec.latency_ffm_date = self.display_timedelta_latency(late_tracking_info_date - rec.ffm_date)
                rec.latency_ffm_date_num = (late_tracking_info_date - rec.ffm_date).days
            else:
                rec.latency_ffm_date = False
                rec.latency_ffm_date_num = False
            if rec.paid_at:
                rec.latency_paid_date = self.display_timedelta_latency(late_tracking_info_date - rec.paid_at)
                rec.latency_paid_date_num = (late_tracking_info_date - rec.paid_at).days
            else:
                rec.latency_paid_date = False
                rec.latency_paid_date_num = False

    def display_timedelta_latency(self, time_cal):
        return str(time_cal.days) + " days, " + str(time_cal.seconds // 3600) + ":" + str((time_cal.seconds // 60) % 60)

    def action_confirm_shipping_address(self):
        self.order_id.action_confirm_shipping_address()

    def action_cancel_order_line(self):
        self.sol_status = 'cancelled'

    def get_detail_error_summary(self):
        detail_error = ''
        if not self.is_delivery_name_format:
            detail_error += self.delivery_name or '' + ' '
        if not self.is_us_city:
            detail_error += self.city or '' + ' '
        if not self.is_us_state:
            detail_error += self.state_id.name or '' + ' '
        if not self.is_us_zip_code:
            detail_error += self.zip or '' + ' '
        if not self.is_us_order:
            detail_error += self.country_id.name or '' + ' '
        if not self.is_delivery_street:
            detail_error += self.street or '' + ' '
        return detail_error

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'total_discount')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            quantity = 1.0
            if line.total_discount != 0.0 and line.discount == 0.0:
                price = line.price_unit * line.product_uom_qty - (line.total_discount or 0.0)
            else:
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                quantity = line.product_uom_qty
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, quantity,
                                            product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
            if self.env.context.get('import_file', False) and not self.env.user.user_has_groups(
                    'account.group_account_manager'):
                line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])

    def confirm_address_edit_status(self):
        self.write({
            'sol_status': 'processing',
            'sol_fulfillment_status': 'unexported',
        })
        if 'error' in self.pending_reason.mapped('code'):
            reason_id = self.pending_reason.search([('code', '=', 'error')], limit=1)
            self.write({
                'pending_reason': [(3, reason_id.id)]
            })

    def create_sale_order_line(self, vals):
        sale_order_line = self.env['sale.order.line']
        order_line = {
            'order_id': vals.get('order_id', False),
            'product_id': vals.get('product_id', False),
            'company_id': vals.get('company_id', False),
            'name': vals.get('description', ''),
            'product_uom': vals.get('product_uom')
        }

        new_order_line = sale_order_line.new(order_line)
        new_order_line.product_id_change()
        order_line = sale_order_line._convert_to_write({name: new_order_line[name] for name in new_order_line._cache})
        order_line.update({
            'order_id': vals.get('order_id', False),
            'product_uom_qty': vals.get('order_qty', 0.0),
            'price_unit': vals.get('price_unit', 0.0),
            'total_discount': vals.get('total_discount', 0.0),
            'product_sku': vals.get('product_sku'),
            'state': 'draft',
        })
        return order_line

    def action_processing_sale_order_line(self):
        self.sol_status = 'processing'
        self.sol_fulfillment_status = 'unexported'
        return True

    def action_fail_order_line(self):
        self.sol_status = 'failed'
        return True

    def action_pending_order_line(self):
        self.sol_status = 'pending'
        self.sol_fulfillment_status = 'pending_export'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        res = self.filtered(lambda line: line.order_id.is_create_picking)
        return super(SaleOrderLine, res)._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)

    # @api.depends('date_order')
    def check_order_duplicate(self):
        day_of_duplicate = self.env.user.company_id.day_of_duplicate
        if not day_of_duplicate or not self.partner_shipping_id:
            return
        date_order_duplicate = self.date_order - timedelta(days=day_of_duplicate)
        domain = [('email', '=', self.email), ('date_order', '>=', date_order_duplicate),
                  ('order_id', '!=', self.order_id.id), ('product_tmpl_id', '=', self.product_tmpl_id.id),
                  ('sol_status', 'not in', ['failed', 'cancelled'])]
        order_line_lst = self.search(domain)

        if order_line_lst:
            self.order_id.set_status_order_duplicate()
            self.set_status_order_line_pending(self.order_id.get_pending_reason('duplicate_sol', 'Duplicate Sale Order Line'))
            for order_id in order_line_lst.order_id:
                order_id.set_status_order_duplicate()
                order_id.order_line.set_status_order_line_pending()
            order_line_lst.set_status_order_line_pending(self.order_id.get_pending_reason('duplicate_sol', 'Duplicate Sale Order Line'))
            return True
        if self.order_id.order_status == 'pending':
            self.set_status_order_line_pending()
            return True

    def set_status_order_line_pending(self, reason_ids=''):
        for line in self:
            if not reason_ids:
                line.write({
                    'sol_fulfillment_status': 'pending_export',
                    'sol_status': 'pending',
                })
                return True

            line.write({
                'pending_reason': [(6, 0, reason_ids)],
                'sol_fulfillment_status': 'pending_export',
                'sol_status': 'pending',
            })

    def write(self, vals):
        if "tracking_number" in vals:
            vals.update({
                'trackingmore_registed': False,
                'tkm_ffm_status': False,
                'track17_ffm_status': False,
                'register_17track': False,
                'carrier_id': False,
                'tracking_info_ids': [(5,)]
            })
        return super(SaleOrderLine, self).write(vals)

    @api.model
    def create(self, vals):
        res = super(SaleOrderLine, self).create(vals)
        if res.is_extra_line:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            res.product_url = base_url
        res.update_product_url()
        return res

    def send_main_sol_success(self):
        # self.action_send_mail_sol('mail_template_order_line_success')
        self.order_id.action_send_mail_order('mail_template_add_tracking_number')
