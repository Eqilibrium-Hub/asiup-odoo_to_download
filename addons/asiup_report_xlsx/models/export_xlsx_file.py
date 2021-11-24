from odoo import models, fields, _, api


class ExportXlsxFile(models.Model):
    _name = 'export.xlsx.file.store'
    _rec_name = 'name'
    _inherit = 'report.report_xlsx.abstract'

    export_file = fields.Binary("Export File", attachment=False)
    name = fields.Char("Name")

    def get_file_export(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/report/xlsx/export.xlsx.file.store/%s' % self.id,
            'target': 'new',
            'res_id': self.id,
        }