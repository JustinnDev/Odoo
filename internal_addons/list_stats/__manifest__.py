# -*- coding: utf-8 -*-
{
    'name': 'Extension estilo Google Sheet'
    '',
    'summary': 'Estadísticas rápidas (estilo Google Sheets) sobre filas seleccionadas en cualquier lista',
    'description': """
Añade un asistente genérico y reutilizable que, al seleccionar filas en
cualquier vista de lista de Odoo y usar el menú "Acciones" (⚙️), muestra
en un popup la Suma, el Promedio, la Cantidad, el Máximo y el Mínimo de
todos los campos numéricos de esas filas.

Este módulo NO depende de ningún módulo de negocio. Para habilitarlo en
un modelo específico, el módulo dueño de ese modelo debe depender de
'list_stats' y agregar un registro ir.actions.act_window con
binding_model_id apuntando a su modelo (ver README.md).
    """,
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'author': 'Tu Empresa',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/list_stats_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}