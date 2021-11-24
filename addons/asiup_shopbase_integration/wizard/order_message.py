from odoo import fields, models, api


class OrderMessageWizard(models.TransientModel):
    _name = "order.message.wizard"
    _description = "Message wizard to display warnings, alert ,success messages"

    def get_default(self):
        if self.env.context.get("message", False):
            return self.env.context.get("message")
        return False

    name = fields.Text(string="Message", readonly=True, default=get_default)
    type_message = fields.Char()
    pending_reason = fields.Many2many('pending.request.reason', string='Pending Reason', tracking=True)


    def cancel_sale_order(self):
        order_obj = self.env['sale.order'].search([('id', '=', self.env.context.get('active_id'))])
        order_obj.action_cancel_sale_order()
        return True

    def pending_sale_order(self):
        order_obj = self.env['sale.order'].search([('id', '=', self.env.context.get('active_id'))])
        order_obj.action_pending_sale_order()
        if self.pending_reason:
            for reason in self.pending_reason:
                order_obj.write({
                    'pending_reason': [(4, reason.id)]
                })
        return True
