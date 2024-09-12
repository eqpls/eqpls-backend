# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

def config(path, module, config):
    defconf = config['default']
    modconf = config[module]
    envconf = config[f'{module}:environment']
    kcconf = config['keycloak']

    title = defconf['title']
    tenant = defconf['tenant']
    endpoint = defconf['endpoint']
    system_access_key = defconf['system_access_key']
    system_secret_key = defconf['system_secret_key']
    kc_hostname = kcconf['hostname']
    kc_hostport = kcconf['hostport']

    modconf['postcmd'] = f'/bin/sh -c ". /default_user_group; mc alias set --insecure data http://localhost:9000 {system_access_key} \"{system_secret_key}\"; mc admin policy create --insecure data $MINIO_DEFAULT_USER_GROUP_ID /init.d/policy.json;" &>/dev/null'

    envconf['MINIO_ROOT_USER'] = system_access_key
    envconf['MINIO_ROOT_PASSWORD'] = system_secret_key
    envconf['MINIO_BROWSER_REDIRECT_URL'] = f'https://{endpoint}/minio/'
    envconf['MINIO_IDENTITY_OPENID_CONFIG_URL_PRIMARY_IAM'] = f'http://{kc_hostname}:{kc_hostport}/auth/realms/{tenant}/.well-known/openid-configuration'
    envconf['MINIO_IDENTITY_OPENID_CLIENT_ID_PRIMARY_IAM'] = 'minio'
    envconf['MINIO_IDENTITY_OPENID_DISPLAY_NAME_PRIMARY_IAM'] = title
    envconf['MINIO_IDENTITY_OPENID_SCOPES_PRIMARY_IAM'] = 'openid'
    envconf['MINIO_IDENTITY_OPENID_REDIRECT_URI_PRIMARY_IAM'] = f'https://{endpoint}/minio/oauth/callback'
    envconf['MINIO_IDENTITY_OPENID_CLAIM_USERINFO'] = 'on'
