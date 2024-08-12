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
    path = os.path.dirname(os.path.realpath(__file__))
    config = configparser.ConfigParser()
    config.read(f'{path}/module.ini', encoding='utf-8')
    title = config['default']['title']
    port = config['default']['port']
    res = requests.get(f'http://localhost:{port}/{title}/health')
    res.raise_for_status()
    result = res.json()
    if not result['healthy']: raise Exception()
except: exit(1)
else: exit(0)
