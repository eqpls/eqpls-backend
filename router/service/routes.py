# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import os

from fastapi import WebSocket

from .controls import Control

#===============================================================================
# SingleTone
#===============================================================================
ctrl = Control(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.websocket(f'{ctrl.uri}/websocket')
async def connect_websocket(
    socket:WebSocket,
    token: str,
    org: str
):
    await ctrl.registerWSockConnection(socket, token, org)
