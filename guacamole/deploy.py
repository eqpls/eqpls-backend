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

    guacd_hostname = config['guacd']['hostname']
    guacd_hostport = config['guacd']['hostport']

    database_hostname = config['postgresql']['hostname']
    database_hostport = config['postgresql']['hostport']

    kc_hostname = config['keycloak']['hostname']
    kc_hostport = config['keycloak']['hostport']
    kc_auth_endpoint = f'https://{endpoint}/auth/realms/{tenant}/protocol/openid-connect/auth'
    kc_jwks_endpoint = f'http://{kc_hostname}:{kc_hostport}/realms/{tenant}/protocol/openid-connect/certs'
    kc_issuer = f'https://{endpoint}/auth/realms/{tenant}'
    kc_redirect_uri = f'https://{endpoint}/static/html/terminal.html'

    environment = [
        f'GUACD_HOSTNAME={guacd_hostname}',
        f'GUACD_PORT={guacd_hostport}',
        f'POSTGRESQL_HOSTNAME={database_hostname}',
        f'POSTGRESQL_PORT={database_hostport}',
        f'POSTGRESQL_USER={system_access_key}',
        f'POSTGRESQL_PASSWORD={system_secret_key}',
        'POSTGRESQL_DATABASE=guacamole',
        'POSTGRESQL_AUTO_CREATE_ACCOUNTS=true',
        f'OPENID_AUTHORIZATION_ENDPOINT={kc_auth_endpoint}',
        f'OPENID_JWKS_ENDPOINT={kc_jwks_endpoint}',
        f'OPENID_REDIRECT_URI={kc_redirect_uri}',
        f'OPENID_ISSUER={kc_issuer}',
        f'OPENID_CLIENT_ID=guacamole',
        f'OPENID_USERNAME_CLAIM_TYPE=preferred_username',
        'EXTENSION_PRIORITY=*,openid'
    ]

    ports = {
        f'{hostport}/tcp': (hostaddr, hostport)
    } if export else {}

    volumes = [
        f'{path}/{module}/conf.d:/conf.d',
        f'{path}/{module}/data.d:/data.d',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': 'echo "OK" || exit 1',
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
