from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    products = env['product.product'].search([('purchase_ok', '=', True)])
    env['reception.price.list.line']._ensure_lines(products)
