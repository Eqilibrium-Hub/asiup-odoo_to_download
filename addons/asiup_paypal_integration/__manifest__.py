# -*- coding: utf-8 -*-
{
    'name': "Asiup paypal integration",

    'summary': """
      Manage multiple paypal account and credentials""",

    'description': """
        Asiup Paypal Integration
    """,

    'author': "Suplo Team",
    'website': "https://suplo.vn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/asiup_paypal.xml',
        'views/res_config_settings_paypal.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
