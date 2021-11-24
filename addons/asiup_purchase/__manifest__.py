# -*- coding: utf-8 -*-
{

    'name': 'Asiup Purchase',
    'summary': 'Asiup Purchase',
    'description': 'Asiup Purchase',
    'category': 'Purchase',
    'version': '14.0.1.0.0',

    'author': "Suplo Team",
    'website': "https://suplo.vn",
    'depends': ['base', 'mail', 'woo_commerce_ept'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/pack_configs_views.xml',
        'views/supplier_manage_view.xml',
        'views/supplier_price_list_view.xml',
        'views/sale_order_line_view.xml',
        'views/asiup_product_view.xml',
        'views/asiup_quotation_view.xml',
        # 'views/import_quotation_view.xml',
    ],
}
