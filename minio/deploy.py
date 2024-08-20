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

    minio_browser_redirect_uri = f'https://{endpoint}/minio/ui/'

    kc_hostname = config['keycloak']['hostname']
    kc_hostport = config['keycloak']['port']
    kc_openid_config_url = f'http://{kc_hostname}:{kc_hostport}/realms/{tenant}/.well-known/openid-configuration'
    kc_openid_client_id = 'minio'
    # kc_openid_client_secret = 'AE9x8lEmWwuAy7g4jwLqCVxZXOKY6jvF'
    kc_openid_display_name = title
    kc_openid_scopes = 'openid'
    kc_openid_redirect_uri = f'https://{endpoint}/minio/ui/oauth_callback'
    kc_openid_claim_userinfo = 'on'

    environment = [
        f'MINIO_ROOT_USER={system_access_key}',
        f'MINIO_ROOT_PASSWORD={system_secret_key}',
        f'MINIO_BROWSER_REDIRECT_URL={minio_browser_redirect_uri}',
        f'MINIO_IDENTITY_OPENID_CONFIG_URL_PRIMARY_IAM={kc_openid_config_url}',
        f'MINIO_IDENTITY_OPENID_CLIENT_ID_PRIMARY_IAM={kc_openid_client_id}',
        # f'MINIO_IDENTITY_OPENID_CLIENT_SECRET_PRIMARY_IAM={kc_openid_client_secret}',
        f'MINIO_IDENTITY_OPENID_DISPLAY_NAME_PRIMARY_IAM={kc_openid_display_name}',
        f'MINIO_IDENTITY_OPENID_SCOPES_PRIMARY_IAM={kc_openid_scopes}',
        f'MINIO_IDENTITY_OPENID_REDIRECT_URI_PRIMARY_IAM={kc_openid_redirect_uri}',
        f'MINIO_IDENTITY_OPENID_CLAIM_USERINFO={kc_openid_claim_userinfo}'
    ]

    ports = {
        f'{port}/tcp': (host, port)
    } if export else {}

    volumes = [
        f'{path}/{module}/init.d:/init.d',
        f'{path}/{module}/conf.d:/conf.d',
        f'{path}/{module}/data.d:/data',
        f'{path}/{module}/back.d:/back.d'
    ]

    healthcheck = {
        'test': 'curl -k -f -I http://localhost:9000/minio/health/live || exit 1',
        'interval': health_check_interval * 1000000000,
        'timeout': health_check_timeout * 1000000000,
        'retries': health_check_retries
    }

    restart_policy = {
        'Name': 'on-failure',
        'MaximumRetryCount': 5
    }

    command = 'server --console-address :9001 /data'
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
    post_exec = f'/bin/sh -c "mc alias set --insecure data http://localhost:9000 {system_access_key} "{system_secret_key}"; mc admin policy create --insecure data admin /init.d/policy_admin.json; mc admin policy create --insecure data user /init.d/policy_user.json; mc mb --insecure data/shared; mc mb --insecure data/{system_access_key}; mc mb --insecure data/{admin_username};" &>/dev/null'

    return (f'{tenant}/{module}:{version}', command, options, post_exec)
