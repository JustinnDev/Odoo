{
    'name': 'Nota de Recepción',
    'version': '1.0',
    'category': 'Purchases',
    'summary': 'Registro de recepciones en patio con generación automática de órdenes de compra',
    'description': """
        Módulo para gestionar notas de recepción de materiales.
        Permite registrar pesajes, calcular totales por producto con descuento
        y generar una orden de compra a partir de los totales.
    """,
    'author': 'Tu Empresa',
    'depends': ['purchase', 'stock', 'list_stats'],  # stock para los productos, purchase para generar PO
    'data': [
        'security/ir.model.access.csv',
        'security/reception_note_security.xml',
        'data/ir_sequence.xml',
        'views/reception_note_views.xml',
        'views/menu_views.xml',
        'views/list_stats_bindings.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,

}