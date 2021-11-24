from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def _check_twilio_whatsapp(self):
        result = self.env['ir.module.module'].search(
            [('name', '=', 'twilio_whatsapp_integration')])
        if result:
            return True
        else:
            return False

    module_twilio_whatsapp_integration = fields.Boolean(
        string='Install Twilio Whatsapp Integration',
        help='It will Install Twilio Whatsapp Integration automatically.',
        default=False)
    is_twilio_whatsapp_in_addon = fields.Boolean(default=_check_twilio_whatsapp)
