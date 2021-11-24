from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import time
from datetime import datetime
import pytz
import requests
import json
from dateutil import parser

utc = pytz.utc


class PendingRequest(models.Model):
    _name = "pending.request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # _rec_name = 'sale_order_id'
    _description = 'Pending Request'

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
    pending_reason = fields.Many2many('pending.request.reason', string='Pending Reason')

    def name_get(self):
        result = []
        for pending in self:
            name = pending.request_date.strftime("%d/%m/%Y") + '-' + pending.state
            result.append((pending.id, name))
        return result

    state = fields.Selection([
        ('draft', u'Draft'),
        ('requested', u'Requested'),
        ('approved', u'Approved'),
        ('resumed', u'Resumed'),
        ('rejected', u'Rejected')], default='draft', string='State', tracking=True, copy=False)

    def save_request(self):
        self.state = 'requested'
        return {'type': 'ir.actions.act_window_close'}

    def do_approval(self):
        self.sale_order_id.pending_so_from_pending_request()
        self.state = 'approved'

    def do_reject(self):
        self.state = 'rejected'

    def unlink(self):
        for rec in self:
            if rec.state != 'requested':
                raise ValidationError(_('Can"t remove a request not in state "requested"!'))
        return super(PendingRequest, self).unlink()


class PendingRequestReason(models.Model):
    _name = "pending.request.reason"

    name = fields.Char(string='Pending Reason')
    code = fields.Char(string='Pending Code')


class SaleOrder(models.Model):
    _inherit = "sale.order"

    pending_request_count = fields.Integer(string='Number of Pending Request', compute='_compute_pending_request')

    def action_view_pending_request(self):
        self.ensure_one()
        return {
            'name': _('Pending Request of %s', self.name),
            'res_model': 'pending.request',
            'type': 'ir.actions.act_window',
            'context': {'default_sale_order_id': self.id},
            'domain': [('id', 'in', self.pending_request_ids.ids)],
            'view_mode': 'tree,form',
        }

    @api.depends('cancel_request_ids')
    def _compute_pending_request(self):
        for rec in self:
            rec.pending_request_count = len(rec.pending_request_ids)
