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

    database_hostname = config['postgresql']['hostname']

    with open(f'{path}/{module}/conf.d/keycloak.conf', 'w') as fd:
        fd.write(f"""
db=postgres
db-username={system_access_key}
db-password={system_secret_key}
db-url=jdbc:postgresql://{database_hostname}/keycloak
http-enabled=true
hostname=https://{endpoint}/auth
hostname-admin=https://{endpoint}/auth
hostname-strict=false
hostname-backchannel-dynamic=true
proxy-headers=xforwarded
        """)

    environment = [
        f'KEYCLOAK_ADMIN={system_access_key}',
        f'KEYCLOAK_ADMIN_PASSWORD={system_secret_key}',
        f'KC_HEALTH_ENABLED=true',
    ]

    ports = {
        f'{port}/tcp': (host, port)
    } if export else {}

    volumes = [
        f'{path}/{module}/conf.d/keycloak.conf:/opt/keycloak/conf/keycloak.conf',
        f'{path}/{module}/data.d:/data.d',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': '[ -f /tmp/HealthCheck.java ] || echo "public class HealthCheck { public static void main(String[] args) throws java.lang.Throwable { System.exit(java.net.HttpURLConnection.HTTP_OK == ((java.net.HttpURLConnection) new java.net.URL(args[0]).openConnection()).getResponseCode() ? 0 : 1); } }" > /tmp/HealthCheck.java && java /tmp/HealthCheck.java http://localhost:9000/health/live',
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
