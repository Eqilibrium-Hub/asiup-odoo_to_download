from odoo import fields, models, _
from odoo.exceptions import ValidationError, UserError
import base64
import xlrd


class OrderLineProduct(models.TransientModel):
    _name = 'import.tracking.number'
    _description = 'import tracking number'

    supplier = fields.Char(string='Supplier')
    file_upload = fields.Binary(string='File upload')
    file_name = fields.Char(string='File Name')

    def process_import_tracking_number_webhook(self, data):
        sku = data.get("sku")
        order_name = data.get("order_name")
        supplier = data.get("supplier")
        tracking_number = data.get("tracking_number")
        if not tracking_number:
            raise UserError("Missing tracking number")
        if not order_name:
            raise UserError("Missing order number")
        if not sku:
            raise UserError("Missing sku")
        if not supplier:
            raise UserError("Missing Supplier")
        order_line_id = self.env['sale.order.line'].search([('product_sku', '=', sku), ('order_id.name', '=', order_name)])
        if not order_line_id:
            raise UserError("Not found sale order line")

        supplier_id = self.create_or_update_supplier(supplier)
        order_line_id.supplier = supplier_id

        self.set_status_order_with_track(order_line_id, tracking_number)

    def create_or_update_supplier(self, name):
        supplier_obj = self.env['res.partner']
        supplier_id = supplier_obj.search([('name', '=', name)], limit=1)
        if supplier_id:
            return supplier_id.id
        supplier_id = supplier_obj.create({
            'name': name,
            'supplier_rank': 1
        })
        return supplier_id.id

    def action_import_tracking_number(self):
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
                supplier = sheet.cell_value(row, 2).strip()
                tracking_number = sheet.cell_value(row, 3).strip()
                data = {
                    "order_name": order_name,
                    "sku": sku,
                    "supplier": supplier,
                    "tracking_number": tracking_number,
                }
            except Exception as e:
                raise UserError(str(e))
            self.with_delay(
                description=f'Process import new tracking number {tracking_number} - {order_name}').process_import_tracking_number_webhook(data)
        return {
            'name': _('Queue Job Import Tracking Number'),
            'view_mode': 'tree',
            'view_id': self.env.ref('queue_job.view_queue_job_tree').id,
            'res_model': 'queue.job',
            'domain': [['name', 'like', "Process import new tracking number"]],
            'context': "{'search_default_group_by_state':1}",
            'type': 'ir.actions.act_window',
            'target': 'main',
        }

        # if count == error_count == 0:
        #     raise UserError(_('Import file is empty!'))
        # else:
        #     return self.show_success_msg(count, error_count)

    @staticmethod
    def set_status_order_with_track(order_line_obj, tracking_number):
        order_line_obj.write({
            'tracking_number': str(tracking_number),
            'sol_delivery_status': 'error'
        })

    def check_format_file_excel(self, file_name):
        if file_name.endswith('.xls') is False and file_name.endswith('.xlsx') is False and file_name.endswith(
                '.xlsb') is False:
            self.file_upload = None
            self.file_name = None
            raise UserError(_("File format not support, should be 'xlsx' or 'xlsb' or 'xls'"))

    def template_file_import_example(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/asiup_report_xlsx/static/Upload_TKN.xlsx'
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "_parent",
        }

    def show_success_msg(self, counter, error_count):
        # open the new success message box
        view = self.env.ref('sh_message_wizard.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Checking number imported successfully\n  "
        if error_count > 0:
            dic_msg += str(error_count) + " Lines unable to import \n"
        context['message'] = dic_msg

        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }
