from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PlantaBale(models.Model):
    _name = 'planta.bale'
    _description = 'Paca'
    _order = 'start_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
    )
    material_type_id = fields.Many2one(
        'product.product',
        string='Tipo de Material',
        required=True,
    )
    weight = fields.Float(
        string='Peso',
        digits='Product Unit of Measure',
        help='Peso de la paca en kg.',
    )
    state = fields.Selection([
        ('in_process', 'En Proceso'),
        ('available', 'Disponible'),
        ('dispatched', 'Despachada'),
        ('cancel', 'Cancelada'),
    ], string='Estado', default='in_process', tracking=True)
    start_date = fields.Datetime(
        string='Fecha de Inicio',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )
    finish_date = fields.Datetime(
        string='Fecha de Finalización',
        readonly=True,
    )
    duration = fields.Float(
        string='Duración (horas)',
        compute='_compute_duration',
        store=True,
        readonly=True,
    )
    position_x = fields.Float(
        string='Posición X',
        digits='Float',
        help='Coordenada X de la posición en planta.',
    )
    position_y = fields.Float(
        string='Posición Y',
        digits='Float',
        help='Coordenada Y de la posición en planta.',
    )
    creator_ids = fields.Many2many(
        'hr.employee',
        string='Creadores',
        help='Operadores que participaron en la creación de la paca.',
    )

    payment_state = fields.Selection([
    ('unpaid', 'Sin Pagar'),
    ('paid', 'Pagada'),
    ], string='Estado de Pago', default='unpaid', tracking=True)

    note = fields.Text(string='Notas')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('planta.bale') or _('Nuevo')
        return super().create(vals_list)

    @api.depends('start_date', 'finish_date')
    def _compute_duration(self):
        for bale in self:
            if bale.finish_date and bale.start_date:
                duration = bale.finish_date - bale.start_date
                bale.duration = duration.total_seconds() / 3600.0
            else:
                bale.duration = 0.0

    @api.constrains('weight')
    def _check_weight(self):
        for bale in self:
            if bale.weight and bale.weight <= 0:
                raise ValidationError(_('El peso de la paca debe ser positivo.'))

    def action_available(self):
        """Marca la paca como disponible usando los campos de la vista."""
        self.ensure_one()
        if self.state != 'in_process':
            raise UserError(_('Solo se puede marcar como disponible una paca en proceso.'))
        if not self.weight or self.weight <= 0:
            raise UserError(_('Debe registrar un peso positivo antes de marcar como disponible.'))
        if not self.creator_ids:
            raise UserError(_('Debe añadir al menos un creador.'))

        self.write({
            'finish_date': fields.Datetime.now(),
            'state': 'available',
        })

    def action_set_in_process(self):
        """Vuelve a poner la paca en estado En Proceso."""
        self.ensure_one()
        if self.state != 'available':
            raise UserError(_('Solo se puede volver a En Proceso desde Disponible.'))
        self.write({
            'state': 'in_process',
            'finish_date': False,
        })

    def action_dispatch(self):
        """Marca la paca como despachada."""
        self.ensure_one()
        if self.state != 'available':
            raise UserError(_('Solo se puede despachar una paca disponible.'))
        self.state = 'dispatched'

    def action_cancel(self):
        """Cancela la paca."""
        self.ensure_one()
        if self.state not in ['in_process', 'available']:
            raise UserError(_('Solo se puede cancelar una paca en proceso o disponible.'))
        self.state = 'cancel'

    def action_set_paid(self):
        """Marca la paca como pagada."""
        self.ensure_one()
        if self.state not in ['available', 'dispatched']:
            raise UserError(_('Solo se puede pagar una paca disponible o despachada.'))
        self.payment_state = 'paid'

    def action_set_unpaid(self):
        """Marca la paca como sin pagar."""
        self.ensure_one()
        self.payment_state = 'unpaid'