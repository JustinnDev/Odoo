#!/usr/bin/env python3
import os
import re
import shutil
import psutil

CONF_PATH = os.environ.get("ODOO_CONF", "C:/Odoo/Odoo/odoo.conf")
DB_ON_SAME_HOST = True        # ¿PostgreSQL corre en este mismo servidor?

MB = 1024 ** 2
AVG_WORKER_RAM = 350 * MB     # consumo medio de un worker (estimación de Odoo)


def get_cpu_count():
    try:
        return len(os.sched_getaffinity(0))   # respeta límites de cpuset
    except AttributeError:
        return os.cpu_count() or 1


def calculate_settings():
    cpu = get_cpu_count()
    total_ram = psutil.virtual_memory().total
    usable_ram = total_ram * (0.70 if DB_ON_SAME_HOST else 0.90)

    workers_by_cpu = max(2, cpu)
    workers_by_ram = max(2, int(usable_ram // AVG_WORKER_RAM))
    workers = min(workers_by_cpu, workers_by_ram)

    cron_threads = 1 if workers <= 2 else 2
    total_procs = workers + cron_threads + 1       # +1 = proceso gevent/longpolling

    per_proc = usable_ram / total_procs
    hard = int(min(2560 * MB, max(1024 * MB, per_proc * 2)))   # sobreasignación x2
    soft = int(hard * 0.8)

    return {
        "workers": workers,
        "max_cron_threads": cron_threads,
        "limit_memory_soft": soft,
        "limit_memory_hard": hard,
        "limit_time_cpu": 60,
        "limit_time_real": 120,
    }


def update_conf(path, values, section="options"):
    """Actualiza solo las claves indicadas; el resto del archivo queda intacto."""
    lines = []
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()

    header_re = re.compile(r"^\s*\[(.+?)\]\s*$")
    key_re = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*[=:]")

    # Localizar la sección [options]
    start = end = None
    for i, line in enumerate(lines):
        m = header_re.match(line)
        if not m:
            continue
        if start is None:
            if m.group(1).strip().lower() == section:
                start = i
        else:
            end = i
            break

    if start is None:                      # no existe la sección: crearla
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{section}]")
        start = len(lines) - 1
    if end is None:
        end = len(lines)

    # Reemplazar las claves que ya existen
    pending = dict(values)
    for i in range(start + 1, end):
        m = key_re.match(lines[i])
        if m and m.group(1).lower() in pending:
            key = m.group(1)
            lines[i] = f"{key} = {pending.pop(key.lower())}"

    # Añadir las que faltan al final de la sección (antes de líneas en blanco)
    if pending:
        pos = end
        while pos > start + 1 and not lines[pos - 1].strip():
            pos -= 1
        lines[pos:pos] = [f"{k} = {v}" for k, v in pending.items()]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    settings = calculate_settings()
    update_conf(CONF_PATH, settings)
    print(f"{CONF_PATH} actualizado:")
    for k, v in settings.items():
        print(f"  {k} = {v}")