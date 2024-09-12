# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

def config(path, module, config):
    defconf = config['default']
    envconf = config[f'{module}:environment']
    psqlconf = config['postgresql']

    endpoint = defconf['endpoint']
    system_access_key = defconf['system_access_key']
    system_secret_key = defconf['system_secret_key']
    psql_hostname = psqlconf['hostname']

    envconf['KEYCLOAK_ADMIN'] = system_access_key
    envconf['KEYCLOAK_ADMIN_PASSWORD'] = system_secret_key
    envconf['KC_HEALTH_ENABLED'] = 'true'

    with open(f'{path}/{module}/conf.d/keycloak.conf', 'w') as fd: fd.write(\
f'''
db=postgres
db-username={system_access_key}
db-password={system_secret_key}
db-url=jdbc:postgresql://{psql_hostname}/keycloak
http-enabled=true
http-relative-path=/auth
hostname=https://{endpoint}/auth
hostname-admin=https://{endpoint}/auth
hostname-strict=false
hostname-backchannel-dynamic=true
proxy-headers=xforwarded
''')
