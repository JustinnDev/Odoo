{
    'name': 'Nota de Entrega',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Registro de despachos con generación automática de órdenes de venta',
    'description': """
        Módulo para gestionar notas de despacho de materiales.
        Permite registrar pesajes, calcular totales por producto con descuento
        y generar una orden de venta a partir de los totales.
    """,
    'author': 'Tu Empresa',
    'depends': ['sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/dispatch_note_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}