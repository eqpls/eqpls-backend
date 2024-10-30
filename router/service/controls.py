# -*- coding: utf-8 -*-
'''
@copyright: Equal Plus
@author: Hye-Churn Jang
'''

try: import LOG  # @UnresolvedImport
except: pass
#===============================================================================
# Import
#===============================================================================
import traceback
from fastapi import WebSocketDisconnect
from common import SessionControl
from driver.redis import RedisAccount, RedisQueue


#===============================================================================
# Implement
#===============================================================================
class Control(SessionControl):

    def __init__(self, path):
        SessionControl.__init__(self, path, RedisAccount)
        self.queue = RedisQueue(self)
        self.userSockets = {}
        self.groupSockets = {}

    async def startup(self):
        await self.queue.connect()
        await self.queue.subscribe(self.listenQueue)

    async def shutdown(self):
        await self.queue.disconnect()

    async def listenQueue(self, category, target, key, val):
        if category == 'group':
            if 'admin' in self.groupSockets:
                for socket in self.groupSockets['admin']:
                    try: await socket.send_json([key, val])
                    except: pass
            if target in self.groupSockets:
                for socket in self.groupSockets[target]:
                    try: await socket.send_json([key, val])
                    except: pass
            LOG.DEBUG(f'send to {self.tenant}:group:{target}')
        elif category == 'user':
            if target in self.userSockets:
                for socket in self.userSockets[target]:
                    try: await socket.send_json([key, val])
                    except: pass
                LOG.DEBUG(f'send to {self.tenant}:user:{target}')

    async def listenSocket(self, socket):
        await socket.accept()
        try: key, token = await socket.receive_json()
        except: await socket.close()
        else:
            if key == 'auth':
                try:
                    authInfo = await self.checkBearerToken(token)
                    username = authInfo.username
                    if username not in self.userSockets: self.userSockets[username] = []
                    self.userSockets[username].append(socket)
                    if authInfo.checkAdmin():
                        if 'admin' not in self.groupSockets: self.groupSockets['admin'] = []
                        self.groupSockets['admin'].append(socket)
                    else:
                        for group in authInfo.groups:
                            if group not in self.groupSockets: self.groupSockets[group] = []
                            self.groupSockets[group].append(socket)
                    await socket.send_json(['status', 'connected'])
                except:
                    try: self.userSockets.remove(socket)
                    except: pass
                    if authInfo.checkAdmin():
                        try: self.groupSockets['admin'].remove(socket)
                        except: pass
                    else:
                        for group in authInfo.groups:
                            try: self.groupSockets[group].remove(socket)
                            except: pass
                    try: await socket.close()
                    except: pass
                else:
                    while True:
                        try:
                            key, val = await socket.receive_json()
                            await self.socketHandler(socket, authInfo, key, val)
                        except WebSocketDisconnect:
                            try: self.userSockets.remove(socket)
                            except: pass
                            for group in authInfo.groups:
                                try: self.groupSockets[group].remove(socket)
                                except: pass
                            break
                        except Exception as e:
                            if LOG.isDebugMode():
                                LOG.DEBUG(e)
                                LOG.DEBUG(traceback.extract_stack()[:-1])
            else: await socket.close()

    async def socketHandler(self, socket, authInfo, key, val):
        socket.send_json([key, val])
