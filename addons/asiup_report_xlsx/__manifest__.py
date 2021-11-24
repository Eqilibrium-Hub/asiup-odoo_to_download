# -*- coding: utf-8 -*-
{
    'name': "asiup_report_xlsx",

    'summary': """
       asiup report xlsx""",

    'description': """
         asiup report xlsx
    """,
    'category': 'Report',
    'version': '14.0.1.0.0',
    'depends': ['base', 'report_xlsx', 'woo_commerce_ept', 'queue_job'],

    'data': [
        'security/ir.model.access.csv',
        'views/report_order_line_product.xml',
        'views/import_tracking_number_views.xml',
        'views/report_order_line_store.xml',
        'views/export_xlsx.xml',
        'views/supplier_invoice_view.xml',
        'views/report_supplier_debit.xml'
    ],
    'application': True,
}
