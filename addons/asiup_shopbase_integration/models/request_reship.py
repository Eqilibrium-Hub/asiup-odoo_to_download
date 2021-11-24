from odoo import models, fields, _, api
import pytz

utc = pytz.utc


class RequestReship(models.Model):
    _name = 'reship.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'sale_order_id'
    _description = 'Cancel Request'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, tracking=True, copy=False,
                                     readonly=True, states={'requested': [('readonly', False)]})
    user_id = fields.Many2one('res.users', string='Request By', default=lambda self: self.env.user, readonly=True,
                              copy=False)
    reship_line_ids = fields.One2many('reship.request.order.line', 'request_reship_id', string='Lines')
    order_status = fields.Selection(related='sale_order_id.order_status')
    fulfillment_status = fields.Selection(related='sale_order_id.fulfillment_status')
    payment_status = fields.Selection(related='sale_order_id.payment_status')
    date_order = fields.Datetime(related='sale_order_id.date_order')
    paid_at = fields.Datetime(related='sale_order_id.paid_at')
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, readonly=True, copy=False)
    reship_reason = fields.Many2many('reship.request.reason', string='Reship Reason')

    state = fields.Selection([
        ('draft', u'Draft'),
        ('requested', u'Requested'),
        ('approved', u'Approved'),
        ('cancelled', u'Cancelled'),
        ('rejected', u'Rejected')], default='draft', string='State', tracking=True, copy=False)

    def save_request(self):
        self.state = 'requested'
        self.sale_order_id.is_reship_order = True
        if self.sale_order_id.request_reship_ids:
            reship_ids = self.sale_order_id.request_reship_ids.ids.append(self.id)
            self.sale_order_id.request_reship_ids = reship_ids
        else:
            self.sale_order_id.request_reship_ids = self.ids
        return {'type': 'ir.actions.act_window_close'}

    def do_approval(self):
        self.state = 'approved'
        self.sale_order_id.approved_from_reship_request()
        self.reship_line_ids.order_line_id.write({
            'sol_fulfillment_status': 'request_tkn',
            'sol_status': 'reship',
        })

    def do_reject(self):
        self.state = 'rejected'
        self.sale_order_id.reject_from_reship_request()

    def do_cancel(self):
        self.state = 'cancelled'


class CancelRequestReason(models.Model):
    _name = "reship.request.reason"

    name = fields.Char(string='Reship Reason')


class RequestReshipLine(models.Model):
    _name = "reship.request.order.line"

    product_id = fields.Many2one('product.product', related='order_line_id.product_id')
    order_line_id = fields.Many2one('sale.order.line')
    request_reship_id = fields.Many2one('reship.request', ondelete='cascade')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    request_reship_ids = fields.Many2many('reship.request', string='Request Reship')
    reship_request_count = fields.Integer(compute='_compute_reship_request')
    is_reship_order = fields.Boolean(default=False)

    @api.depends('request_reship_ids')
    def _compute_reship_request(self):
        for rec in self:
            rec.reship_request_count = len(rec.request_reship_ids)

    def create_reship_request(self):
        line_ids = []
        for rec in self.order_line:
            if rec.is_extra_line:
                continue
            line_ids.append(self.env["reship.request.order.line"].create({
                'order_line_id': rec.id}).id)
        return {
            'res_model': 'reship.request',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_id': self.env.ref('asiup_shopbase_integration.reship_request_form_view').id,
            'context': {'default_sale_order_id': self.id,
                        'default_reship_line_ids': line_ids},
            'target': 'new'
        }

    def approved_from_reship_request(self):
        self.order_status = 'reship'
        # self.request_reship_id.reship_line_ids.order_line_id.sol_fulfillment_status = 'request_tkn'
        return

    def reject_from_reship_request(self):
        # self.sale_order_id.order_status = 'delivered'
        return

    def action_view_reship_request(self):
        self.ensure_one()
        return {
            'name': _('Reship Request of %s', self.name),
            'res_model': 'reship.request',
            'type': 'ir.actions.act_window',
            'context': {'default_sale_order_id': self.id},
            'domain': [('id', 'in', self.request_reship_ids.ids)],
            'view_mode': 'tree,form',
        }
