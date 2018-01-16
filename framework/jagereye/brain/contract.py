import json
from jagereye.util import logging
from jagereye.util import static_util

with open(static_util.get_path('messaging.json'), 'r') as f:
    MESSAGES = json.loads(f.read())


class InvalidRequestType(Exception):
    pass


class InvalidRequestFormat(Exception):
    pass


class API():
    def __init__(self, typename):
        self._typename = typename
        self._msg = MESSAGES['ch_api_brain']
        self._msg_r = MESSAGES['ch_api_brain_reply']

    def validate(self, request):
        # TODO: Add error messages to describe the invalid format
        try:
            if request['command'] == self._msg['START_ANALYZER']:
                if self._typename != request['params']['type']:
                    raise InvalidRequestType
                if not request['params']['source'] or \
                   not request['params']['pipelines']:
                    raise InvalidRequestFormat
            elif request['command'] == self._msg['REQ_ANALYZER_STATUS'] or \
                 request['command'] == self._msg['STOP_ANALYZER']:
                if not request['params']['id']:
                    raise InvalidRequestFormat
            else:
                raise InvalidRequestFormat
        except KeyError as e:
            logging.error('KeyError: {}'.format(e))
            raise InvalidRequestFormat

    def reply_status(self, status, pipelines=None):
        """ return a dict for reply status to api server

        Args:
             status (string): required, the new worker status.
                 The status should be 'create', 'initial', 'hshake_1', 'config', 'ready','running' and 'down'.
             pipelines (list of dict): optional, the enabled pipelines with parameters
        Returns:
            dict: msg for reply to api server
        """

        obj = {
            'result': {
                'code': self._msg_r['REPLY_ANALYZER_STATUS'],
                'type': self._typename,
                'status': status
            }
        }
        if pipelines:
            obj['pipelines'] = pipelines
        return obj

    def reply_not_aval(self):
        obj = {
            'error': {
                'code': self._msg_r['NOT_AVAILABLE']
            }
        }
        return obj

    def reply_not_found(self):
        obj = {
            'error': {
                'code': self._msg_r['NOT_FOUND']
            }
        }
        return obj

    def reply_no_op(self):
        obj = {
            'error': {
                'code': self._msg_r['NO_OP']
            }
        }
        return obj
