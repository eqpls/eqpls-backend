# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from fastapi import WebSocket

from .controls import Control

#===============================================================================
# SingleTone
#===============================================================================
# os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ctrl = Control(__file__)
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.websocket(f'{ctrl.uri}/websocket')
async def connect_websocket(socket:WebSocket):
    await ctrl.registerWSockConnection(socket)
