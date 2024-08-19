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

    environment = []

    ports = {
        f'{port}/tcp': (host, port)
    } if export else {}

    volumes = [
        f'{path}/project.ini:/opt/project.ini',
        f'{path}/{module}:/opt/{module}',
        f'{path}/common:/opt/common',
        f'{path}/driver:/opt/driver',
        f'{path}/schema:/opt/schema',
        f'{path}/{module}/conf.d:/conf.d',
        f'{path}/{module}/data.d:/data.d',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': f'python {module}/health.py',
        'interval': health_check_interval * 1000000000,
        'timeout': health_check_timeout * 1000000000,
        'retries': health_check_retries
    }

    restart_policy = None

    command = f'python {module}'
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
