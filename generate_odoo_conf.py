import os
import multiprocessing
import psutil

# Obtener el número de núcleos de CPU
cpu_cores = multiprocessing.cpu_count()

# Obtener la memoria RAM total en GB
ram_gb = int(psutil.virtual_memory().total / (1024 ** 3))

# Calcular el número de workers
if ram_gb < 4:
    workers = 1
elif ram_gb < 8:
    workers = 2
elif ram_gb < 16:
    workers = 4
elif ram_gb < 32:
    workers = 8
else:
    workers = 16

# Calcular los límites de memoria por worker (en bytes)
limit_memory_soft = min(2147483648, int((ram_gb * 1024 ** 3) / workers * 0.8))  # 80% de la memoria por worker
limit_memory_hard = min(2684354560, int((ram_gb * 1024 ** 3) / workers * 1.0))  # 100% de la memoria por worker

# Calcular el número de hilos para tareas cron
max_cron_threads = 1 if workers <= 2 else 2

# Generar el contenido del archivo odoo.conf
conf_content = f"""
[options]
admin_passwd = $pbkdf2-sha512$600000$uPfe./.fUwrB2FtrLQUgRA$ecwOVH6a6uklaN0ZRYtIbAJJuGu2cJmV7P2Rz2ElnB03JjmkSXwMrzvPYi6efP.VooGhE0XplOfQUWYCAXAPCg
workers = {workers}
limit_memory_soft = {limit_memory_soft}
limit_memory_hard = {limit_memory_hard}
limit_time_cpu = 60
limit_time_real = 120
max_cron_threads = {max_cron_threads}
"""

# Guardar el archivo odoo.conf
with open("odoo.conf", "w") as f:
    f.write(conf_content)

print(f"Archivo odoo.conf generado con {workers} workers y {limit_memory_soft} bytes de límite de memoria.")