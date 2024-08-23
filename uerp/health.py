# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import os
import requests
import configparser

#===============================================================================
# Implement
#===============================================================================
try:
    modPath = os.path.dirname(os.path.abspath(__file__))
    prjPath = os.path.dirname(modPath)
    module = os.path.basename(modPath)

    config = configparser.ConfigParser()
    config.read(f'{prjPath}/project.ini', encoding='utf-8')

    hostport = config[module]['hostport']
    res = requests.get(f'http://localhost:{hostport}/internal/health')
    res.raise_for_status()
    result = res.json()
    if not result['healthy']: raise Exception()
except Exception as e:
    print(e)
    exit(1)
else: exit(0)
