from odoo import api, fields, models, _


class Dispute(models.Model):
    _name = "dispute"
    _rec_name = "transaction_authorization"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Dispute"

    state = fields.Selection([
        ('open', u'Open'),
        ('close', u'Close'),
    ], default='open', string='Status')

    color = fields.Integer('Color')

    dispute_source = fields.Selection([
        ('paypal', u'Paypal'),
        ('stripe', u'Stripe'),
    ], string='Dispute Source')

    transaction_authorization = fields.Char(string='Transaction Authorization')
    amount = fields.Float(string='Amount')
    customer_name = fields.Char(string='Customer Name')
    customer_email = fields.Char(string='Customer Email')
    sale_order_id = fields.Many2one('sale.order', compute='_get_sale_order', string='Sale Order', store=True)

    @api.depends('transaction_authorization')
    def _get_sale_order(self):
        for rec in self:
            sale_order = rec.env['sale.order']
            if rec.transaction_authorization:
                sale_order_id = sale_order.search([('transaction_authorization', '=', rec.transaction_authorization)],
                                                  limit=1)
                rec.sale_order_id = sale_order_id.id if sale_order_id else False
            else:
                rec.sale_order_id = False