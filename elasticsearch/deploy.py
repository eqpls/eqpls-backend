# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

def config(path, module, config):
    defconf = config['default']
    envconf = config[f'{module}:environment']

    envconf['EQPLS_SYSTEM_ACCESS_KEY'] = defconf['system_access_key']
    envconf['EQPLS_SYSTEM_SECRET_KEY'] = defconf['system_secret_key']
