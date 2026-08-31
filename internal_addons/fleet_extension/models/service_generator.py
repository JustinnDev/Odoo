from odoo import models, fields, api, _
from odoo.exceptions import UserError

class FleetServiceGenerator(models.AbstractModel):
    _name = 'fleet.extension.service.generator'
    _description = 'Generador de Servicios de Flota'

    def generate_service(self, vehicle, description, service_type, date, amount,
                        vendor_id=False, purchaser_id=False, odometer=False,
                        notes=False):
        """Genera un servicio de flota vanilla (fleet.vehicle.log.services)."""
        self.ensure_one()
        
        if not vehicle:
            raise UserError(_('Debe especificar un vehículo.'))
        if not description:
            raise UserError(_('Debe especificar una descripción.'))
        if not service_type:
            raise UserError(_('Debe especificar un tipo de servicio.'))
        if not date:
            raise UserError(_('Debe especificar una fecha.'))
        if amount is None or amount < 0:
            raise UserError(_('El monto debe ser un valor positivo.'))
        
        service_vals = {
            'vehicle_id': vehicle.id,
            'description': description,
            'service_type_id': service_type.id,
            'date': date,
            'amount': amount,
            'vendor_id': vendor_id.id if vendor_id else False,
            'purchaser_id': purchaser_id.id if purchaser_id else False,
            'odometer': odometer if odometer else vehicle.odometer or 0,
            'notes': notes or False,
        }
        
        service = self.env['fleet.vehicle.log.services'].create(service_vals)
        service.state = 'done'
        
        return service

    def generate_service_batch(self, vehicle_ids, description, service_type, date,
                               amount, vendor_id=False, purchaser_id=False,
                               odometer=False, notes=False):
        """Genera servicios para múltiples vehículos."""
        services = self.env['fleet.vehicle.log.services']
        
        for vehicle in vehicle_ids:
            service = self.generate_service(
                vehicle=vehicle,
                description=description,
                service_type=service_type,
                date=date,
                amount=amount,
                vendor_id=vendor_id,
                purchaser_id=purchaser_id,
                odometer=odometer,
                notes=notes,
            )
            services += service
        
        return services

    def generate_service_from_dict(self, service_data):
        """Genera un servicio desde un diccionario con los parámetros."""
        return self.generate_service(
            vehicle=service_data.get('vehicle'),
            description=service_data.get('description'),
            service_type=service_data.get('service_type'),
            date=service_data.get('date'),
            amount=service_data.get('amount'),
            vendor_id=service_data.get('vendor_id', False),
            purchaser_id=service_data.get('purchaser_id', False),
            odometer=service_data.get('odometer', False),
            notes=service_data.get('notes', False),
        )