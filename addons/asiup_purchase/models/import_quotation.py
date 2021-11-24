from odoo import models, fields, _
import base64, xlrd
from datetime import datetime
from odoo.exceptions import ValidationError, UserError


class Quotation(models.TransientModel):
    _name = 'import.quotation'
    _description = 'Import Quotation'

    file_upload = fields.Binary(string='File upload')
    file_name = fields.Char(string='File Name')

    def check_or_create_pack_config(self, pack):
        qty = pack.split(' ')[1]
        # pack_env = self.env['purchase.pack.configs']
        # pack_obj = pack_env.search([('qty', '=', qty)])
        # if not pack_obj:
        #     pack_obj = pack_env.create({
        #         'name': pack,
        #         'qty': qty,
        #     })
        return

    def purpose_pack_for_import(self, sheet):
        pack_list = []
        # purpose_pack_for_import
        for col in range(12, sheet.ncols):
            pack = sheet.cell_value(0, col).strip()
            if not pack:
                break
            pack_obj = self.check_or_create_pack_config(pack)
            pack_list.append(pack_obj.id if pack_obj else '')
        return pack_list

    @staticmethod
    def get_string_xlrd_date(date):
        datetime_date = xlrd.xldate.xldate_as_datetime(date, 0)
        date_object = datetime_date.date()
        return date_object.isoformat()

    def action_import_quotation(self):
        if self.file_upload is False:
            raise UserError(_('Import File is empty'))
        self.check_format_file_excel(self.file_name)
        count = 0
        try:
            data = self.file_upload  # tien hanh doc file
            data_file = base64.decodestring(data)
            excel = xlrd.open_workbook(file_contents=data_file)
            sheet = excel.sheet_by_index(0)
        except Exception as e:
            raise UserError(_("Can't load import excel file!"))
        if sheet:
            set_price_list = self.purpose_pack_for_import(sheet)
            vals = {}
            for row in range(1, sheet.nrows):
                count += 1
                try:
                    supplier = sheet.cell_value(row, 0).strip()
                    product_source = sheet.cell_value(row, 1).strip()
                    # carrier_line = sheet.cell_value(row, 4).strip()
                    date_version = sheet.cell_value(row, 5)
                    option_value = sheet.cell_value(row, 6)
                    note = sheet.cell_value(row, 7)
                except Exception as e:
                    raise UserError(_("Your excel file does not match with our format "))
                if not product_source:
                    continue
                supplier_obj = self.env['res.partner'].search([('name', '=', supplier)], limit=1)
                product_obj = self.env['product.template'].search([('name', '=', product_source)], limit=1)
                # carrier_obj = self.env['tracking.courier'].search([('name', '=', carrier_line)], limit=1)
                option_obj = self.env['product.attribute.value'].search([('name', '=', option_value)], limit=1)
                line_ids = []
                for col in range(12, sheet.ncols):
                    price = sheet.cell_value(row, col)
                    if price == 0.0 or not price:
                        continue
                    set_id = set_price_list[col - 12]
                    line_ids.append((0, 0, {
                        'set': set_id,
                        'price': price
                    }))
                vals.update({
                    'name': product_source,
                    'supplier': supplier_obj.id if supplier_obj else False,
                    'note': note,
                    'date_version': self.get_string_xlrd_date(date_version) if date_version else False,
                    'pack_price_ids': line_ids
                })
                quotation = self.env['purchase.quotation'].create(vals)
                if not quotation:
                    continue
        if count == 0:
            raise UserError(_('Import file is empty!'))

    def check_format_file_excel(self, file_name):
        if file_name.endswith('.xls') is False and file_name.endswith('.xlsx') is False and file_name.endswith(
                '.xlsb') is False:
            self.file_upload = None
            self.file_name = None
            raise UserError(_("File format not support, should be 'xlsx' or 'xlsb' or 'xls'"))

    def template_file_import_example(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = base_url + '/asiup_purchase/static/Quotation_list_Upload_to_Odoo.xlsx'
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "_parent",
        }
