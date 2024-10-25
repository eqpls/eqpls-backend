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
from fastapi import HTTPException


#===============================================================================
# Implement
#===============================================================================
class EpException(HTTPException):

    def __init__(self, status_code, message):
        message = str(message)
        HTTPException.__init__(self, status_code, {'message': message})
        LOG.ERROR(f'{status_code}: {message}')
        if LOG.isDebugMode():
            traceback.print_exc()
            LOG.DEBUG(traceback.extract_stack()[:-1])

