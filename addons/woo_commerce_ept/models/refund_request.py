from odoo import fields, models, _
from odoo.exceptions import ValidationError
import pytz
import requests
from dateutil import parser

utc = pytz.utc


class RefundRequest(models.Model):
    _inherit = "refund.request"

    woo_instance_id = fields.Many2one(related='sale_order_id.woo_instance_id', string="Woo Instance", store=True)
    woo_order_id = fields.Char(related='sale_order_id.woo_order_id', string='Woo Order ID')
    # payment_gateway_id = fields.Many2one(related='sale_order_id.payment_gateway_id', string="Woo Payment Gateway")

    refund_woo_at = fields.Datetime(readonly=True, string='Woo Refund At')
    woo_refund_id = fields.Char(string='Woo Refund ID', readonly=True)

    def refund_in_woo(self):
        if not self.woo_instance_id:
            return False
        wc_api = self.woo_instance_id.woo_connect()
        order = self.sale_order_id
        data = {
            "amount": "{:.2f}".format(self.refund_amount),
            'reason': str(self.note or ''),
            'api_refund': False}
        try:
            response = wc_api.post('orders/%s/refunds' % order.woo_order_id, data)
        except Exception as error:
            raise ValidationError(_("Something went wrong while refunding Order.\n\nPlease Check your Connection and "
                              "Instance Configuration.\n\n" + str(error)))

        if not isinstance(response, requests.models.Response):
            raise ValidationError(_("Refund \n Response is not in proper format :: %s") % response)

        if response.status_code in [200, 201]:
            vals = {}
            woo_refund_id = response.json().get("id")
            if woo_refund_id:
                vals.update({'woo_refund_id': woo_refund_id})
            refund_woo_at = response.json().get("date_created")
            if refund_woo_at:
                vals.update({'refund_woo_at': parser.parse(refund_woo_at).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")})
            self.write(vals)
        else:
            raise ValidationError(_("Refund \n%s") % response.content)
        return True
    
    def do_approval(self):
        res = super(RefundRequest, self).do_approval()
        if self.woo_order_id:
            self.refund_in_woo()
            self.sale_order_id.process_refunded_status()
        # if self.refund_amount < self.amount_total:
        #     self.sale_order_id.action_send_mail_order('mail_template_refund_partially')
        #     return res
        # self.sale_order_id.action_send_mail_order('mail_template_refund_fully')
        return res