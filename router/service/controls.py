# -*- coding: utf-8 -*-
'''
Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import
#===============================================================================
import traceback

from fastapi import WebSocketDisconnect

from common import MeshControl


#===============================================================================
# Implement
#===============================================================================
class Control(MeshControl):

    def __init__(self, path):
        MeshControl.__init__(self, path, sessionChecker='uerp')
        self.sockets = {}

    async def startup(self): pass

    async def shutdown(self): pass

    def createWSockPayload(self, key, value): return [key, value]

    async def sendWSockData(self, username, payload):
        if username in self.sockets:
            for socket in self.sockets[username]:
                try: await socket.send_json(payload)
                except: pass

    async def registerWSockConnection(self, socket):
        await socket.accept()
        try: key, value = await socket.receive_json()
        except: await socket.close()
        else:
            if key == 'auth':
                try:
                    org = value['org']
                    token = value['token']
                    authInfo = await self.checkAuthInfo(org, token)
                    username = authInfo.username
                except:
                    traceback.print_exc()
                    await socket.close()
                else:
                    if username not in self.sockets: self.sockets[username] = []
                    self.sockets[username].append(socket)
                    while True:
                        try: await self.parseWSockData(org, token, authInfo, await socket.receive_json())
                        except WebSocketDisconnect:
                            self.sockets[username].remove(socket)
                            break
                        except: traceback.print_exc()
            else: await socket.close()

    async def parseWSockData(self, org, token, authInfo, data):
        key, value = data
        await self.sendWSockData(authInfo.username, self.createWSockPayload(key, value))
