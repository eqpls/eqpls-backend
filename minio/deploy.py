# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

import os

def config(path, module, config):
    try: os.mkdir(f'{path}/{module}/data.d')
    except: pass

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

    envconf['MINIO_ROOT_USER'] = system_access_key
    envconf['MINIO_ROOT_PASSWORD'] = system_secret_key
    envconf['MINIO_BROWSER_REDIRECT_URL'] = f'https://{endpoint}/minio/'
