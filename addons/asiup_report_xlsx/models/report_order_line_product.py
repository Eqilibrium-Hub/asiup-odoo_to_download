from odoo import fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class OrderLineProduct(models.TransientModel):
    _name = 'report.asiup_report_xlsx.report_order_line_product'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'order line to supplier'

    record_ids = fields.Char()

    def generate_xlsx_report(self, workbook, data, records):
        inform = records[0]
        sheet = workbook.add_worksheet('Fulfillment -')
        workbook.formats[0].font_size = 11
        sheet.set_paper(9)  # A4 210 x 297 mm
        sheet.center_horizontally()
        record_ids = inform.record_ids.strip().split(' ')

        data = self.env['sale.order.line'].search(
            [('id', 'in', record_ids)], order='create_date DESC')

        set_font = workbook.add_format({'text_wrap': True, 'border': 1})

        table_header = workbook.add_format({
            'bold': 1, 'text_wrap': 1, 'align': 'center', 'valign': 'vcenter', 'border': 1,
            'fg_color': '#e0e0e0'
        })
        table_number = workbook.add_format({
            'align': 'right',
        })

        sheet.set_column(0, 0, 4)
        sheet.set_column(1, 1, 20)
        sheet.set_column(2, 2, 22)
        sheet.set_column(3, 3, 38)
        sheet.set_column(4, 4, 20)
        sheet.set_column(5, 5, 8)
        sheet.set_column(6, 6, 50)
        sheet.set_column(7, 7, 22)
        sheet.set_column(8, 8, 15)
        sheet.set_column(9, 9, 15)
        sheet.set_column(10, 10, 15)
        sheet.set_column(11, 11, 15)
        sheet.set_column(12, 12, 15)
        sheet.set_column(13, 13, 10)
        sheet.set_column(14, 14, 16)
        sheet.set_column(15, 15, 16)
        sheet.set_column(16, 16, 16)
        sheet.set_column(17, 17, 33)
        sheet.set_column(18, 18, 22)

        date_format = workbook.add_format({'bold': False, 'border': 1, 'text_wrap': True,
                                           'num_format': 'dd-mm-yyyy'})
        row_label = 0
        row_title = row_label + 1
        sheet.set_row(row_title, 50)

        sheet.write(row_title, 0, u'STT', table_header)
        sheet.write(row_title,1, u'Shop Domain', table_header)
        sheet.write(row_title, 2, u"Order Number", table_header)
        sheet.write(row_title, 3, u"Email", table_header)
        sheet.write(row_title, 4, u"Paid At", table_header)
        sheet.write(row_title, 5, u"LineItem Quantity", table_header)
        sheet.write(row_title, 6, u"LineItem Name", table_header)
        sheet.write(row_title, 7, u"LineItem Sku", table_header)
        sheet.write(row_title, 8, u"Billing Name", table_header)
        sheet.write(row_title, 9, u"Billing Address1", table_header)
        sheet.write(row_title, 10, u"Billing Address2", table_header)
        sheet.write(row_title, 11, u"Billing Company", table_header)
        sheet.write(row_title, 12, u"Billing City", table_header)
        sheet.write(row_title, 13, u"Billing Zip", table_header)
        sheet.write(row_title, 14, u"Billing Province", table_header)
        sheet.write(row_title, 15, u"Billing Country", table_header)
        sheet.write(row_title, 16, u"Billing Phone", table_header)
        sheet.write(row_title, 17, u"Trans", table_header)
        sheet.write(row_title, 18, u"Payment Method", table_header)

        for index, line in enumerate(data, start=row_title + 1):
            sheet.write(index, 0, index - row_title, set_font)
            sheet.write(index, 1, line.order_id.primary_domain if line.order_id.primary_domain else '', set_font)
            sheet.write(index, 2, line.order_id.name, set_font)
            sheet.write(index, 3, line.partner_shipping_id.email if line.partner_shipping_id.email else '')
            sheet.write(index, 4, (line.paid_at + timedelta(hours=7)).strftime('%d-%m-%Y %H:%M:%S') if line.paid_at else '', set_font)
            sheet.write(index, 5, line.product_uom_qty if line.product_uom_qty else '', set_font)
            sheet.write(index, 6, line.product_id.display_name if line.product_id.display_name else '', set_font)
            row_size = len(line.product_id.display_name)
            row_max = 0
            if row_size > row_max:
                row_max = row_size
                sheet.set_column(6, 6, row_max)
            sheet.write(index, 7, line.product_sku if line.product_sku else '', set_font)
            sheet.write(index, 8, line.partner_shipping_id.name if line.partner_shipping_id.name else '', set_font)
            sheet.write(index, 9, line.partner_shipping_id.street if line.partner_shipping_id.street else '', set_font)
            sheet.write(index, 10, line.partner_shipping_id.street2 if line.partner_shipping_id.street2 else '',
                        set_font)
            sheet.write(index, 11, line.partner_shipping_id.company_name if line.partner_shipping_id.company_name else '', set_font)
            sheet.write(index, 12, line.partner_shipping_id.city if line.partner_shipping_id.city else '', set_font)
            sheet.write(index, 13, line.partner_shipping_id.zip if line.partner_shipping_id.zip else '', set_font)
            sheet.write(index, 14, line.partner_shipping_id.state_id.code if line.partner_shipping_id.state_id else ' ',
                        set_font)
            sheet.write(index, 15,
                        line.partner_shipping_id.country_id.name if line.partner_shipping_id.country_id else '',
                        set_font)
            sheet.write(index, 16, line.partner_shipping_id.phone if line.partner_shipping_id.phone else '', set_font)
            sheet.write(index, 17, line.order_id.transaction_authorization if line.order_id.transaction_authorization else '', set_font)
            sheet.write(index, 18, line.order_id.payment_gateway_id.name if line.order_id.payment_gateway_id else '')

    def get_report(self):
        if not self.record_ids:
            raise UserError(_('No Record Select'))
        self.check_order_export_status()
        data = self.with_context(active_model='report.asiup_report_xlsx.report_order_line_product').create_xlsx_report(self.ids, {})
        self.env['export.xlsx.file.store'].create({
            'export_file': data[0],
            'name': f'File FFM Export {self.id} - {datetime.now().month}/{datetime.now().day}'
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/xlsx/asiup_report_xlsx.report_order_line_product/%s' % self.id,
            'target': 'new',
            'res_id': self.id,
        }

    def check_order_export_status(self, action=''):
        order_line_ids = self.env['sale.order.line'].search([('id', 'in', self.record_ids.strip().split())])
        if action == 'ffmsent':
            for order_line_id in order_line_ids:
                if order_line_id.sol_fulfillment_status == 'unexported' and order_line_id.sol_status == 'processing':
                    continue
                raise UserError(_(f'Order {order_line_id.order_id.name} is not able to export!'))
        return order_line_ids

    def export_order_line_change_ffmsent(self):
        order_line_ids = self.check_order_export_status('ffmsent')
        if not order_line_ids:
            return
        for order_line_id in order_line_ids:
            order_line_status = set(order_line_id.order_id.order_line.filtered(
                lambda r: r.id != order_line_id.id and r.is_extra_line == False).mapped('sol_fulfillment_status'))
            if 'unexported' in order_line_status:
                order_line_id.order_id.write({
                    'order_status': 'processing',
                    'fulfillment_status': 'partially_exported',
                })
            else:
                order_line_id.order_id.write({
                    'order_status': 'processing',
                    'fulfillment_status': 'exported',
                })
            if not order_line_id.ffm_date:
                order_line_id.ffm_date = fields.Datetime.now() - timedelta(hours=15)
            order_line_id.write({'sol_fulfillment_status': 'exported',
                                  'sol_status': 'processing'})
        return self.get_report()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def action_generate_order_line(self):
        form_view_id = self.env.ref("asiup_report_xlsx.asiup_report_order_product_wizard").id
        ids = ''
        for order_line_id in self._context.get('active_ids'):
            ids += str(order_line_id) + ' '

        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'report.asiup_report_xlsx.report_order_line_product',
            'views': [(form_view_id, 'form')],
            'target': 'new',
            'context': {'default_record_ids': ids}
        }
