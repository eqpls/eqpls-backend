# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import os
import sys
import uvicorn
import configparser

#===============================================================================
# Implement
#===============================================================================
def run():
    modPath = os.path.dirname(os.path.abspath(__file__))
    module = os.path.basename(modPath)
    prjPath = os.path.abspath(f'{modPath}/..')
    iniPath = os.path.abspath(f'{prjPath}/project.ini')
    schPath = os.path.abspath(f'{prjPath}/schema')

    config = configparser.ConfigParser()
    config.read(iniPath, encoding='utf-8')
    stage = config['default']['stage']
    modConf = config[module]

    os.chdir(modPath)
    sys.path.append(prjPath)

    uvicorn.run(
        'service.routes:api',
        host=modConf['host'],
        port=int(modConf['port']),
        loop='uvloop' if 'container' in modConf['runtime'] else 'auto',
        workers=int(modConf['workers']) if 'dev' not in stage else None,
        reload=True if 'dev' in stage else False,
        reload_dirs=[schPath, modPath] if 'dev' in stage else None,
        log_level='debug' if 'dev' in stage else 'info'
    )
