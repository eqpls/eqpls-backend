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
    hostaddr = modconf['hostaddr']
    hostport = int(modconf['hostport'])
    export = int(modconf['export']) if modconf['export'] and modconf['export'].lower() != 'false' else None
    memory = modconf['memory']

    environment = [
        f'discovery.type=single-node'
    ]

    ports = {
        f'{hostport}/tcp': (hostaddr, hostport)
    } if export else {}

    volumes = [
        f'{path}/{module}/conf.d:/conf.d',
        #f'{path}/{module}/data.d:/usr/share/elasticsearch/data',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': 'curl -k https://localhost:9200 || exit 1',
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
    post_exec = f'/usr/share/elasticsearch/bin/elasticsearch-users useradd {system_access_key} -p "{system_secret_key}" -r superuser -s'

    return (f'{tenant}/{module}:{version}', command, options, post_exec)
