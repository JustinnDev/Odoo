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
        'views/reception_note_summary_tree_standalone.xml',
        'views/reception_note_line_summary_actions.xml',
        'views/reception_note_views.xml',
        'views/menu_views.xml',
        'views/list_stats_bindings.xml',
        'views/reception_note_line_summary_bindings.xml',
        'report/reception_note_report.xml',
        'report/reception_note_report_no_unit_price.xml',
        'report/reception_note_report_no_price.xml',
        'report/reception_note_report_simple.xml'
    ],

    'installable': True,
    'application': True,
    'auto_install': False,

}