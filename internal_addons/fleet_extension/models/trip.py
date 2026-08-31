from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetExtensionTrip(models.Model):
    _name = 'fleet.extension.trip'
    _description = 'Viaje de Vehículo'
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo'),
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehículo',
        required=True,
    )
    fuel_tank_id = fields.Many2one(
        'fleet.extension.fuel_tank',
        string='Tanque de Combustible',
        compute='_compute_fuel_tank',
        store=True,
    )
    start_location_id = fields.Many2one(
        'fleet.extension.location',
        string='Origen',
    )
    destination_location_id = fields.Many2one(
        'fleet.extension.location',
        string='Destino',
    )
    driver_id = fields.Many2one(
        'res.partner',
        string='Conductor',
        required=True,
    )
    start_date = fields.Datetime(
        string='Fecha de Salida',
    )
    destination_date = fields.Datetime(
        string='Fecha de Llegada a Destino',
    )
    arrival_date = fields.Datetime(
        string='Fecha de Regreso',
    )
    initial_fuel = fields.Float(
        string='Combustible Inicial',
        digits='Product Unit of Measure',
        readonly=True,
    )
    final_fuel = fields.Float(
        string='Combustible Final',
        digits='Product Unit of Measure',
    )
    fuel_consumption = fields.Float(
        string='Consumo de Combustible',
        compute='_compute_fuel_consumption',
        store=True,
        digits='Product Unit of Measure',
        readonly = True
    )
    state = fields.Selection([
        ('scheduled', 'Programado'),
        ('in_process', 'En Proceso'),
        ('complete', 'Completado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='scheduled', tracking=True)
    internal_note = fields.Text(string='Nota Interna')

    check_fuel_state = fields.Selection([
        ('unverified', 'Sin Comprobar'),
        ('verified', 'Comprobado'),
    ], string='Estado del Combustible', default='unverified', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fleet.extension.trip') or _('Nuevo')
        return super().create(vals)

    @api.depends('vehicle_id')
    def _compute_fuel_tank(self):
        for trip in self:
            tank = self.env['fleet.extension.fuel_tank'].search([
                ('vehicle_id', '=', trip.vehicle_id.id)
            ], limit=1)
            trip.fuel_tank_id = tank.id if tank else False

    @api.depends('initial_fuel', 'final_fuel')
    def _compute_fuel_consumption(self):
        for trip in self:
            if trip.final_fuel is not None:
                trip.fuel_consumption = trip.initial_fuel - trip.final_fuel
            else:
                trip.fuel_consumption = 0.0

    def action_start(self):
        """Inicia el viaje registrando la fecha y combustible inicial."""
        self.ensure_one()
        if self.state != 'scheduled':
            raise UserError(_('Solo se puede iniciar un viaje programado.'))
        if not self.start_date:
            self.start_date = fields.Datetime.now()
        if not self.initial_fuel:
            self.initial_fuel = self.fuel_tank_id.current_fuel

        # Verificar si el conductor es diferente al asignado actualmente
        if self.vehicle_id.driver_id != self.driver_id:
            # Cerrar el historial anterior si existe
            last_assignment = self.env['fleet.vehicle.assignation.log'].search([
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date_end', '=', False),
            ], limit=1, order='date_start desc')
            
            if last_assignment:
                # Cerrar la asignación anterior
                last_assignment.date_end = self.start_date or fields.Datetime.now()
            
            self.vehicle_id.driver_id = self.driver_id
            
        self.state = 'in_process'

    def action_in_destination(self):
        """Registra la llegada al destino."""
        self.ensure_one()
        if self.state != 'in_process':
            raise UserError(_('El viaje debe estar en proceso.'))
        self.destination_date = fields.Datetime.now()

    def action_arrival(self):
        """Registra el regreso a la empresa."""
        self.ensure_one()
        if self.state != 'in_process':
            raise UserError(_('El viaje debe estar en proceso.'))
        self.arrival_date = fields.Datetime.now()
        self.state = 'complete'

    def action_fuel_check(self):
        """Registra el combustible final al regresar."""
        self.ensure_one()
        if self.final_fuel < 0:
            raise UserError(_('El combustible final no puede ser negativo.'))

        self.check_fuel_state = 'verified'
        
        # Actualizar el tanque del vehículo
        if self.fuel_tank_id:
            self.fuel_tank_id.current_fuel = self.final_fuel

    def action_cancel(self):
        """Cancela el viaje."""
        self.ensure_one()
        self.state = 'cancel'