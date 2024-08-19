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
    module = os.path.basename(modPath)
    prjPath = os.path.abspath(f'{modPath}/..')
    iniPath = os.path.abspath(f'{prjPath}/project.ini')

    config = configparser.ConfigParser()
    config.read(iniPath, encoding='utf-8')

    port = config[module]['port']
    res = requests.get(f'http://localhost:{port}/{module}/health')
    res.raise_for_status()
    result = res.json()
    if not result['healthy']: raise Exception()
except Exception as e:
    print(e)
    exit(1)
else: exit(0)
