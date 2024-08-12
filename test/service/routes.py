# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import os
from fastapi import Request
from .controls import Control

#===============================================================================
# SingleTone
#===============================================================================
ctrl = Control(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.get(f'{ctrl.uri}/hello', tags=['Hello'])
async def get_hello(request:Request) -> dict:
    return {
        'result': 'Hello World!!!'
    }

