# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
from fastapi import WebSocketDisconnect

from common import MeshControl, AsyncRest


#===============================================================================
# Implement
#===============================================================================
class Control(MeshControl):

    def __init__(self, modPath):
        MeshControl.__init__(self, modPath)
        kcHostname = self.config['keycloak']['hostname']
        kcHostport = self.config['keycloak']['port']
        self._kcBaseUrl = f'http://{kcHostname}:{kcHostport}'
        self._sockets = {}

    async def startup(self): pass

    async def shutdown(self): pass

    async def sendWSockData(self, username, key, value):
        if username not in self._sockets: return None
        payload = {'k': key, 'v': value}
        for socket in self._sockets[username]:
            try: socket.send_json(payload)
            except: pass
        return payload

    async def registerWSockConnection(self, socket, token, org):
        async with AsyncRest(self._kcBaseUrl) as rest:
            userinfo = await rest.get(f'/realms/{org}/protocol/openid-connect/userinfo', headers={'Authorization': f'Bearer {token}'})
        username = userinfo['preferred_username']
        await socket.accept()
        if username not in self._sockets: self._sockets[username] = []
        self._sockets[username].append(socket)
        while True:
            try: await self.parseWSockData(token, org, await socket.receive_json())
            except WebSocketDisconnect:
                self._sockets[username].remove(socket)
                break

    async def parseWSockData(self, token, org, data):
        key = data['k']
        value = data['v']
        for username in self._sockets.keys(): self.sendWSockData(username, key, value)
