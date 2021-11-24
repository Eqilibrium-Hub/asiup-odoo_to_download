{
    'name': 'Asiup Stripe Integration',
    'summary': 'Asiup Stripe Integration',
    'description': 'Asiup Stripe Integration',
    'category': 'Integration',
    'version': '14.0.1.0.0',
    'depends': ['asiup_dispute'],
    'external_dependencies': {'python': ['stripe']},
    'data': [
        'security/ir.model.access.csv',
        'views/stripe_account.xml',
        # 'views/dispute_view.xml',
    ],
    'application': True,

}
