def migrate(cr, version):
    for table in [
        'reception_price_list_line',
        'reception_price_list',
        'reception_price_list_column',
        'reception_price_list_value',
        'reception_global_price_list_line',
        'reception_global_price_list',
    ]:
        cr.execute('DROP TABLE IF EXISTS %s CASCADE' % table)
