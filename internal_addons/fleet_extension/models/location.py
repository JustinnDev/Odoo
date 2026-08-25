from odoo import models, fields


class FleetExtensionLocation(models.Model):
    _name = 'fleet.extension.location'
    _description = 'Ubicación para Viajes'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    address = fields.Text(string='Dirección')
    gps_url = fields.Char(string='URL GPS')