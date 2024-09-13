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
    envconf = config[f'{module}:environment']
    volconf = config[f'{module}:volumes']

    envconf['DATABASE_USER'] = defconf['system_access_key']
    envconf['POSTGRES_PASSWORD'] = defconf['system_secret_key']
    volconf['./postgresql/init.d'] = '/init.d'

    with open(f'{path}/{module}/conf.d/postgresql.conf', 'w') as fd:
        fd.write(f'''
listen_addresses = '*'
timezone = 'Etc/UTC'
log_timezone = 'Etc/UTC'
datestyle = 'iso, mdy'
default_text_search_config = 'pg_catalog.english'
max_wal_size = 1GB
min_wal_size = 80MB
wal_level = 'logical'
''')
