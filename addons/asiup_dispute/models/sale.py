from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    dispute_ids = fields.One2many('dispute', 'sale_order_id', string='Disputes')
    dispute_count = fields.Integer(string='Dispute Count', compute='_get_dispute', readonly=True)

    @api.depends("dispute_ids")
    def _get_dispute(self):
        for rec in self:
            rec.dispute_count = len(rec.dispute_ids)

    def action_view_dispute(self):
        disputes = self.mapped('dispute_ids')
        action = self.env["ir.actions.actions"]._for_xml_id("asiup_dispute.dispute_action")
        if len(disputes) > 1:
            action['domain'] = [('id', 'in', disputes.ids)]
        elif len(disputes) == 1:
            form_view = [(self.env.ref('asiup_dispute.dispute_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = disputes.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action