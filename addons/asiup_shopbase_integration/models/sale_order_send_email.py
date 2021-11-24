from odoo import models, fields, api, _
import random
from odoo.exceptions import UserError
from datetime import timedelta


class SaleOrder(models.Model):
    _inherit = "sale.order"

    time_send_mail_tracking = fields.Datetime()

    def action_send_mail_order_change_detail(self):
        action = self.action_send_mail_order('mail_template_order_change_detail')
        view = self.env.ref('sh_message_wizard.sh_message_wizard')
        context = dict(self._context or {})
        if action:
            msg = " Email send successfully\n"
            name = "Success"
        else:
            msg = "Email send not success,\n Please contact to admin"
            name = "Failed"
        context['message'] = msg
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def action_cancel_sale_order(self):
        result = super(SaleOrder, self).action_cancel_sale_order()
        # self.action_send_mail_order('mail_template_order_cancel')
        return result

    def action_multi_mail_order_success(self):
        order_lst = self.search([(self._context.get('active_ids'))])
        for order in order_lst:
            order.action_send_mail_order('mail_template_order_create')

    def action_send_mail_order(self, template):
        template_id = self.env['ir.model.data'].xmlid_to_res_id('asiup_shopbase_integration.' + template, raise_if_not_found=False)
        if not template_id:
            return False
        self.with_context().message_post_with_template(template_id=template_id,
                                                       model='sale.order', res_id=self.id,
                                                       composition_mode='mass_mail',
                                                       **{'tracking_mail': True})
        return True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_send_mail = fields.Boolean(string='Send To Cus', compute='_compute_is_send_mail')
    send_mail_ids = fields.One2many('mail.mail', 'res_id', string='Send Mails')
    send_mail_count = fields.Integer(string='Email Count', compute='_compute_email_count')
    is_send_mail_order_line_delivery = fields.Boolean(default=False)

    def _compute_is_send_mail(self):
        for rec in self:
            rec.is_send_mail = any([mail.state == 'sent' for mail in rec.send_mail_ids])

    def _compute_email_count(self):
        for rec in self:
            rec.send_mail_count = len(rec.send_mail_ids)

    def action_view_send_mail(self):
        self.ensure_one()
        send_mail_ids = self.send_mail_ids.ids
        action = {
            'name': _('Mail send of sale order line %s', self.name),
            'res_model': 'mail.mail',
            'type': 'ir.actions.act_window',
            'context': {'default_res_id': self.id, 'model': 'sale.order.line'},
            'domain': [('id', 'in', send_mail_ids)],
            'view_mode': 'tree,form',
        }
        return action

    def action_send_mail_sol(self, template):
        template_id = self.env['ir.model.data'].xmlid_to_res_id('asiup_shopbase_integration.' + template, raise_if_not_found=False)
        if not template_id:
            return False
        self.order_id.with_context(line=self.id).message_post_with_template(template_id=template_id,
                                                                            model='sale.order', res_id=self.order_id.id,
                                                                            composition_mode='mass_mail',
                                                                            **{'tracking_mail': True})
        return True

    def write(self, vals):
        res = super(SaleOrderLine, self).write(vals)
        if vals.get('sol_delivery_status') == 'delivered':
            for rec in self:
                rec.with_delay(eta=5, description='Send email delivery order process!').send_mail_delivery_order()
        return res

    def send_mail_delivery_order(self):
        if self.is_send_mail_order_line_delivery:
            return True
        self.action_send_mail_sol('mail_template_order_line_success')
        self.order_id.with_context(line=self.id).send_message_sms(self.order_id.with_context(line=self.id), self.partner_shipping_id,
                                                                'order_success')
        self.is_send_mail_order_line_delivery = True
        return True
