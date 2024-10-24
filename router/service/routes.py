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
ctrl = Control(__file__)
api = ctrl.api


#===============================================================================
# API Interfaces
#===============================================================================
@api.websocket(f'{ctrl.uriver}/websocket')
async def listenSocket(socket:WebSocket): await ctrl.listenSocket(socket)
