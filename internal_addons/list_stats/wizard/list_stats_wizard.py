from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Tipos de campo que consideramos "numéricos" y por lo tanto calculables
NUMERIC_FIELD_TYPES = ('integer', 'float', 'monetary')

# Campos técnicos que casi nunca interesa agregar (aunque sean numéricos)
EXCLUDED_FIELD_NAMES = ('id',)


class ListStatsWizard(models.TransientModel):
    """Wizard genérico y reutilizable: calcula Suma, Promedio, Cantidad,
    Máximo y Mínimo de un conjunto de registros seleccionados (active_ids)
    de CUALQUIER modelo.

    Por defecto analiza TODOS los campos numéricos del modelo. Un binding
    puede restringir la lista de campos pasando contexto en el propio
    ir.actions.act_window:

      - 'list_stats_fields': lista blanca de nombres técnicos de campo.
         Si se define, SOLO esos campos se analizan (en ese orden no
         importa, se muestran alfabéticamente por etiqueta igual).
      - 'list_stats_exclude_fields': lista negra de nombres técnicos de
         campo a excluir del análisis automático. Se ignora si ya se usó
         'list_stats_fields'.

    Ejemplo de binding limitando campos:
        <record id="action_list_stats_wizard_mi_modelo" model="ir.actions.act_window">
            <field name="name">Ver Estadísticas</field>
            <field name="res_model">list.stats.wizard</field>
            <field name="view_mode">form</field>
            <field name="target">new</field>
            <field name="binding_model_id" ref="model_mi_modelo"/>
            <field name="binding_view_types">list</field>
            <field name="context">{'list_stats_fields': ['total_kg', 'total_amount']}</field>
        </record>

    Vive en el módulo independiente `list_stats` y no depende de ningún
    módulo de negocio. Para habilitarlo en un modelo, el módulo dueño de
    ese modelo debe:
      1) depender de 'list_stats' en su __manifest__.py
      2) agregar un ir.actions.act_window con binding_model_id apuntando
         a su modelo y binding_view_types='list'.
    Ver README.md del módulo list_stats para el ejemplo exacto.
    """
    _name = 'list.stats.wizard'
    _description = 'Estadísticas de Selección'

    model_name = fields.Char(string='Modelo', readonly=True)
    model_display_name = fields.Char(string='Modelo (Nombre)', readonly=True)
    record_count = fields.Integer(string='Registros Seleccionados', readonly=True)
    line_ids = fields.One2many(
        'list.stats.wizard.line',
        'wizard_id',
        string='Estadísticas',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []

        if not active_model:
            raise UserError(_(
                'No se pudo determinar el modelo de origen. '
                'Abra este asistente desde el menú de Acciones de una lista.'
            ))
        if not active_ids:
            raise UserError(_(
                'Debe seleccionar al menos un registro (marque las casillas '
                'de la lista) antes de ver las estadísticas.'
            ))

        target_model = self.env[active_model]
        records = target_model.browse(active_ids).exists()

        if not records:
            raise UserError(_('Los registros seleccionados ya no existen.'))

        # Contexto opcional para restringir qué campos se analizan.
        # Si el binding define 'list_stats_fields', se usa como lista
        # blanca exclusiva; si no, se usa 'list_stats_exclude_fields'
        # como lista negra adicional a EXCLUDED_FIELD_NAMES.
        allowed_fields = self.env.context.get('list_stats_fields')
        excluded_fields = set(EXCLUDED_FIELD_NAMES)
        excluded_fields.update(self.env.context.get('list_stats_exclude_fields') or [])

        fields_info = target_model.fields_get()
        stats_lines = []

        for fname, finfo in fields_info.items():
            if allowed_fields is not None:
                # Lista blanca activa: solo se procesan estos campos,
                # ignorando incluso EXCLUDED_FIELD_NAMES (si el binding
                # los pidió explícitamente, se respeta su elección).
                if fname not in allowed_fields:
                    continue
            else:
                if fname in excluded_fields:
                    continue
            if finfo.get('type') not in NUMERIC_FIELD_TYPES:
                continue
            values = []
            for rec in records:
                try:
                    val = rec[fname]
                except Exception:
                    continue
                if isinstance(val, bool):
                    # Los booleanos son subtipo de int en Python; los
                    # descartamos explícitamente para no ensuciar los stats.
                    continue
                if val is False or val is None:
                    val = 0.0
                values.append(float(val))

            if not values:
                continue

            count = len(values)
            total = sum(values)
            stats_lines.append((0, 0, {
                'field_name': fname,
                'field_label': finfo.get('string') or fname,
                'sum_value': total,
                'avg_value': total / count if count else 0.0,
                'count_value': count,
                'max_value': max(values),
                'min_value': min(values),
            }))

        # Ordenar alfabéticamente por etiqueta para una lectura más natural
        stats_lines.sort(key=lambda t: t[2]['field_label'])

        res.update({
            'model_name': active_model,
            'model_display_name': fields_info and target_model._description or active_model,
            'record_count': len(records),
            'line_ids': stats_lines,
        })
        return res


class ListStatsWizardLine(models.TransientModel):
    """Una fila de resultado por cada campo numérico analizado."""
    _name = 'list.stats.wizard.line'
    _description = 'Línea de Estadística de Selección'
    _order = 'field_label'

    wizard_id = fields.Many2one(
        'list.stats.wizard',
        string='Asistente',
        required=True,
        ondelete='cascade',
    )
    field_name = fields.Char(string='Campo (técnico)', readonly=True)
    field_label = fields.Char(string='Campo', readonly=True)
    sum_value = fields.Float(string='Suma', readonly=True, digits=(16, 3))
    avg_value = fields.Float(string='Promedio', readonly=True, digits=(16, 3))
    count_value = fields.Integer(string='Cantidad', readonly=True)
    max_value = fields.Float(string='Máximo', readonly=True, digits=(16, 3))
    min_value = fields.Float(string='Mínimo', readonly=True, digits=(16, 3))