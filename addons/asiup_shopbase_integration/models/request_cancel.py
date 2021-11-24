from odoo import api, fields, models, _
import pytz

utc = pytz.utc


class CancelRequest(models.Model):
    _name = "cancel.request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'sale_order_id'
    _description = 'Cancel Request'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, tracking=True, copy=False,
                                    readonly=True, states={'requested': [('readonly', False)]})
    user_id = fields.Many2one('res.users', string='Request By', default=lambda self: self.env.user, readonly=True,
                              copy=False)

    order_status = fields.Selection(related='sale_order_id.order_status')
    fulfillment_status = fields.Selection(related='sale_order_id.fulfillment_status')
    payment_status = fields.Selection(related='sale_order_id.payment_status')
    date_order = fields.Datetime(related='sale_order_id.date_order')
    paid_at = fields.Datetime(related='sale_order_id.paid_at')
    request_date = fields.Date(string='Request Date', default=fields.Date.context_today, readonly=True, copy=False)
    cancel_reason = fields.Many2many('cancel.request.reason', string='Cancel Reason')

    state = fields.Selection([
        ('draft', u'Draft'),
        ('requested', u'Requested'),
        ('approved', u'Approved'),
        ('cancelled', u'Cancelled'),
        ('rejected', u'Rejected')], default='draft', string='State', tracking=True, copy=False)

    def save_request(self):
        self.state = 'requested'
        return {'type': 'ir.actions.act_window_close'}

    def do_approval(self):
        self.state = 'approved'
        self.sale_order_id.cancel_from_cancel_request(status_invoice=False)

    def do_reject(self):
        self.state = 'rejected'
        self.sale_order_id.cancel_from_cancel_request(status_invoice=True)


class CancelRequestReason(models.Model):
    _name = "cancel.request.reason"

    name = fields.Char(string='Cancel Reason')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cancel_request_count = fields.Integer(string='Number of Cancel Request', compute='_compute_cancel_request')

    def action_view_cancel_request(self):
        self.ensure_one()
        return {
            'name': _('Cancel Request of %s', self.name),
            'res_model': 'cancel.request',
            'type': 'ir.actions.act_window',
            'context': {'default_sale_order_id': self.id},
            'domain': [('id', 'in', self.cancel_request_ids.ids)],
            'view_mode': 'tree,form',
        }

    @api.depends('cancel_request_ids')
    def _compute_cancel_request(self):
        for rec in self:
            rec.cancel_request_count = len(rec.cancel_request_ids)
