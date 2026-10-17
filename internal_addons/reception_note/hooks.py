def post_init_hook(env):
    products = env['product.product'].search([('purchase_ok', '=', True)])
    env['reception.price.list.line']._ensure_lines(products)
