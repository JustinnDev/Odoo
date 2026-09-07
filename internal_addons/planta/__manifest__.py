{
    'name': 'Planta',
    'version': '1.0',
    'category': 'Operations',
    'summary': 'Gestión de planta - Pacas y operaciones',
    'description': """
        Módulo de gestión de planta 100% adaptado.
        Control de pacas, produccion, materiales, operadores y posiciones en planta.
    """,
    'author': 'Tu Empresa',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'stock',
        'mail',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/bale_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}