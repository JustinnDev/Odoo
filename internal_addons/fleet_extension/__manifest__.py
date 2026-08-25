{
    'name': 'Extensión de Flota',
    'version': '1.0',
    'category': 'Fleet',
    'summary': 'Tanques de combustible virtuales y viajes para vehículos',
    'description': """
        Extiende el módulo de flota añadiendo tanques de combustible virtuales
        que consumen productos de inventario y viajes con seguimiento de combustible.
    """,
    'author': 'Tu Empresa',
    'depends': ['fleet', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/location_views.xml',
        'views/fuel_tank_views.xml',
        'views/trip_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}