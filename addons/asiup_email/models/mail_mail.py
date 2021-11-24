# -*- coding: utf-8 -*-

from odoo import api, models, fields, tools, _


class MailMail(models.Model):
    _inherit = "mail.mail"

    tracking_mail = fields.Boolean(string='Tracking Mail', default=False)


class MailTemplate(models.Model):
    _inherit = "mail.template"

    active = fields.Boolean('Active', default=True)
    tracking_mail_template = fields.Boolean(string='Tracking Mail Template', default=False)
    condition = fields.Selection([
        ('new_sale_order', 'New Sale Order'),
        ('change_sale_order', 'Sale Order Info Change'),
        ('new_tracking', 'Add Tracking Number'),
        ('change_tracking', 'Change Tracking Number'),
        ('refund_order', 'Refund Order'),
        ('refund_partially','Refund Partially'),
        ('cancel_order', 'Cancel Order'),
        ('order_line_success', 'Order Line Success')
    ], string='Condition', required=True)

    @api.onchange('condition')
    def onchange_condition(self):
        for obj in self:
            if obj.condition:
                if obj.condition in ['order_line_success']:
                    model_id = self.env['ir.model'].search(
                        [('model', '=', 'sale.order.line')])
                    obj.model_id = model_id.id if model_id else False
                    obj.lang = '${object.partner_id.lang}'
            else:
                model_id = self.env['ir.model'].search(
                    [('model', '=', 'sale.order')])
                obj.model_id = model_id.id if model_id else False
                obj.lang = '${object.partner_id.lang}'


class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    tracking_mail = fields.Boolean(string='Tracking Mail', default=False)
    
    def get_mail_values(self, res_ids):
        res = super(MailComposer, self).get_mail_values(res_ids)
        for res_id in res_ids:
            res[res_id].update({'tracking_mail': self.tracking_mail})
        return res