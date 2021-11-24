from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    paypal_live_mode = fields.Boolean(string='PayPal Live')

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(paypal_live_mode=get_param('asiup_paypal_integration.paypal_live_mode') if get_param(
            'asiup_paypal_integration.paypal_live_mode') else '')
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('asiup_paypal_integration.paypal_live_mode',
                                                         self.paypal_live_mode)
