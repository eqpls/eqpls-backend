# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

def config(path, module, config):
    defconf = config['default']
    modconf = config[module]

    system_access_key = defconf['system_access_key']
    system_secret_key = defconf['system_secret_key']
    modconf['postcmd'] = f'/usr/share/elasticsearch/bin/elasticsearch-users useradd {system_access_key} -p "{system_secret_key}" -r superuser -s'
