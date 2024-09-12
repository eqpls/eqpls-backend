# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

def config(path, module, config):
    defconf = config['default']
    envconf = config[f'{module}:environment']
    gcdconf = config['guacd']
    psqlconf = config['postgresql']
    kcconf = config['keycloak']

    tenant = defconf['tenant']
    endpoint = defconf['endpoint']
    kc_hostname = kcconf['hostname']
    kc_hostport = kcconf['hostport']

    envconf['GUACD_HOSTNAME'] = gcdconf['hostname']
    envconf['GUACD_PORT'] = gcdconf['hostport']
    envconf['POSTGRESQL_HOSTNAME'] = psqlconf['hostname']
    envconf['POSTGRESQL_PORT'] = psqlconf['hostport']
    envconf['POSTGRESQL_USER'] = defconf['system_access_key']
    envconf['POSTGRESQL_PASSWORD'] = defconf['system_secret_key']
    envconf['POSTGRESQL_DATABASE'] = 'guacamole'
    envconf['POSTGRESQL_AUTO_CREATE_ACCOUNTS'] = 'true'
    envconf['OPENID_ISSUER'] = f'https://{endpoint}/auth/realms/{tenant}'
    envconf['OPENID_CLIENT_ID'] = 'guacamole'
    envconf['OPENID_USERNAME_CLAIM_TYPE'] = 'preferred_username'
    envconf['OPENID_AUTHORIZATION_ENDPOINT'] = f'https://{endpoint}/auth/realms/{tenant}/protocol/openid-connect/auth'
    envconf['OPENID_JWKS_ENDPOINT'] = f'http://{kc_hostname}:{kc_hostport}/auth/realms/{tenant}/protocol/openid-connect/certs'
    envconf['OPENID_REDIRECT_URI'] = f'https://{endpoint}/static/html/terminal.html'
    envconf['EXTENSION_PRIORITY'] = '*,openid'
