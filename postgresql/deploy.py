# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''


def parameters(module, path, config):
    default = config['default']
    modconf = config[module]

    title = default['title']
    tenant = default['tenant']
    endpoint = default['endpoint']
    version = default['version']
    stage = default['stage']
    system_access_key = default['system_access_key']
    system_secret_key = default['system_secret_key']
    admin_username = default['admin_username']
    admin_password = default['admin_password']
    health_check_interval = int(default['health_check_interval'])
    health_check_timeout = int(default['health_check_timeout'])
    health_check_retries = int(default['health_check_retries'])

    hostname = modconf['hostname']
    host = modconf['host']
    port = int(modconf['port'])
    export = True if modconf['export'].lower() == 'true' else False
    memory = modconf['memory']

    with open(f'{path}/{module}/conf.d/postgresql.conf', 'w') as fd:
        fd.write(f"""
listen_addresses = '*'
timezone = 'Etc/UTC'
log_timezone = 'Etc/UTC'
datestyle = 'iso, mdy'
default_text_search_config = 'pg_catalog.english'
max_wal_size = 1GB
min_wal_size = 80MB
wal_level = 'logical'
        """)

    environment = [
        f'DATABASE_USER={system_access_key}',
        f'POSTGRES_PASSWORD={system_secret_key}'
    ]

    ports = {
        f'{port}/tcp': (host, port)
    } if export else {}

    volumes = [
        f'{path}/{module}/init.d:/init.d',
        f'{path}/{module}/conf.d:/conf.d',
        f'{path}/{module}/data.d:/var/lib/postgresql/data',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': 'pg_isready --username postgres || exit 1',
        'interval': health_check_interval * 1000000000,
        'timeout': health_check_timeout * 1000000000,
        'retries': health_check_retries
    }

    restart_policy = {
        'Name': 'on-failure',
        'MaximumRetryCount': 5
    }

    command = None
    options = {
        'detach': True,
        'name': f'{tenant}-{module}',
        'hostname': hostname,
        'network': tenant,
        'mem_limit': memory,
        'ports': ports,
        'environment': environment,
        'volumes': volumes,
        'healthcheck': healthcheck,
        'restart_policy': restart_policy
    }
    post_exec = None

    return (f'{tenant}/{module}:{version}', command, options, post_exec)
