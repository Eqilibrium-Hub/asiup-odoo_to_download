from odoo import fields, models, _
from odoo.exceptions import ValidationError, UserError
import base64
import xlrd


class OrderLineProduct(models.TransientModel):
    _name = 'import.delivery.status'
    _description = 'import delivery status'

    supplier = fields.Char(string='Supplier')
    file_upload = fields.Binary(string='File upload')
    file_name = fields.Char(string='File Name')

    def process_import_sol_delivery_status(self, data):
        sku = data.get("sku")
        order_name = data.get("order_name")
        sol_delivery_status = data.get("sol_delivery_status")
        if not sku:
            raise UserError("Missing tracking number")
        if not order_name:
            raise UserError("Missing order number")
        if not sol_delivery_status:
            raise UserError("Missing Delivery Status")
        if sol_delivery_status not in ['Pending', 'Not Found', 'Transit', 'Pickup', 'Delivered', 'Expired', 'Undelivered', 'Exception', 'Alert',
                                       'Error']:
            raise UserError(f"Delivery Status not match {sol_delivery_status}")
        order_line_id = self.env['sale.order.line'].search([('product_sku', '=', sku),('order_id.name', '=', order_name)])
        if not order_line_id:
            raise UserError("Not found sale order line")
        order_line_id.sol_delivery_status = sol_delivery_status.lower()

    def action_import_delivery_status(self):
        if self.file_upload is False:
            raise UserError(_('Import File is empty'))
        self.check_format_file_excel(self.file_name)
        try:
            data = self.file_upload  # tien hanh doc file
            data_file = base64.decodestring(data)
            excel = xlrd.open_workbook(file_contents=data_file)
            sheet = excel.sheet_by_index(0)
        except Exception as e:
            raise UserError(_("Can't load import excel file !"))
        if not sheet:
            return False
        for row in range(1, sheet.nrows):
            try:
                order_name = sheet.cell_value(row, 0).strip()
                sku = sheet.cell_value(row, 1).strip()
                sol_delivery_status = sheet.cell_value(row, 2).strip()
                data = {
                    "order_name": order_name,
                    "sku": sku,
                    "sol_delivery_status": sol_delivery_status,
                }
            except Exception as e:
                raise UserError(str(e))
            self.with_delay(
                description=f'Process import new Delivery Status {sol_delivery_status} - {order_name}').process_import_sol_delivery_status(data)
        return {
            'name': _('Queue Job Import Delivery Status'),
            'view_mode': 'tree',
            'view_id': self.env.ref('queue_job.view_queue_job_tree').id,
            'res_model': 'queue.job',
            'domain': [['name', 'like', "Process import new Delivery Status"]],
            'context': "{'search_default_group_by_state':1}",
            'type': 'ir.actions.act_window',
            'target': 'main',
        }

    def check_format_file_excel(self, file_name):
        if file_name.endswith('.xls') is False and file_name.endswith('.xlsx') is False and file_name.endswith(
                '.xlsb') is False:
            self.file_upload = None
            self.file_name = None
            raise UserError(_("File format not support, should be 'xlsx' or 'xlsb' or 'xls'"))

    def template_file_import_example(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/asiup_report_xlsx/static/Upload_Status.xlsx'
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "_parent",
        }
