import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
import json

from jagereye.util import logging


# Loading messaging
with open('../../../services/messaging.json', 'r') as f:
    MESSAGES = json.loads(f.read())

# NATS channels
CH_API_TO_BRAIN = "ch_api_brain"

CH_PUBLIC_BRAIN = "ch_brain"

CH_WORKER_TO_BRAIN = ""
CH_BRAIN_TO_WORKER = ""

CH_BRAIN_TO_RES = "ch_brain_res"
CH_RES_TO_BRAIN = "ch_res_brain"


pending_jobs = {}


def msg_to_json(msg):
    """convert msg received from nats into json

    """
    # TODO(Ray): what if cannot decode()?
    msg = msg.decode()
    # TODO(Ray): what if json cannot loads?
    return json.loads(msg.replace("'", '"'))
    # TODO(Ray): check the receive msg

class Brain(object):
    """Brain the base class for brain service.

    It provides basic interactions to api-server, workers, resource-mgr.
    Like handshake to workers.

    Attributes:

    """
    def __init__(self, ch_public="public_brain", mq_host='nats://localhost:4222'):
        """initial the brain service

        Args:
            ch_public (str): the public nats channel for listening all workers
            mq_host (str): the host and port of nats server
        """
        self._main_loop = asyncio.get_event_loop()
        # TODO(Ray): check NATS is connected to server, error handler
        # TODO(Ray): check mq_host is valid
        self._nats_cli = NATS()
        self._ch_public = ch_public
        self._redis_cli = None
        self._mq_host = mq_host

    async def _setup(self):
        """register all handler

        """
        await self._nats_cli.connect(io_loop=self._main_loop, servers=[self._mq_host])
        await self._nats_cli.subscribe(CH_API_TO_BRAIN, cb=self._api_handler)
        await self._nats_cli.subscribe(CH_PUBLIC_BRAIN, cb=self._public_brain_handler)
        await self._nats_cli.subscribe(CH_RES_TO_BRAIN, cb=self._res_handler)

    async def _private_worker_handler(self, recv):
        """asychronous handler for private channel with each workers

        listen to the private channel with each workers,
        and interact depends on the received msg

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                mst (msg): message
        """
        ch = recv.subject
        reply = recv.reply
        msg = msg_to_json(recv.data)

        # and change the status of the worker
        verb = msg["verb"]
        context = msg["context"]

        if verb == "hshake-3":
            logging.debug("Received 'hshake-3' in private_brain_handler(): '{subject} {reply}': {data}".\
                format(subject=ch, reply=reply, data=msg))

            logging.debug("finish handshake")
            # TODO(Ray): change worker status in DB
            # assign job to worker
            assign_req = {
                "verb": "assign",
                "context": {
                    "workerID": context["workerID"]
                }
            }
            # TODO(Ray): channel need to be get by search DB with workerID
            await self._nats_cli.publish("ch_brain_"+context["workerID"], str(assign_req).encode())
        elif verb == "hbeat":
            # TODO: need to update to DB
            logging.debug("hbeat: "+str(msg))

    async def _public_brain_handler(self, recv):
        """asychronous handler for public channel all initial workers

        listen to the public channel,
        which is for a worker registers to brain when the worker initializing

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                mst (msg): message
        """

        ch = recv.subject
        reply = recv.reply
        msg = msg_to_json(recv.data)
        # TODO(Ray): check the receive msg
        # and change the status of the worker

        verb = msg["verb"]
        context = msg["context"]

        if verb == "hshake-1":
            logging.debug("Received 'hshake-1' msg in _public_brain_handler(): '{subject} {reply}': {data}".\
                    format(subject=ch, reply=reply, data=msg))
            # TODO: check if context has the keys "ch_to..."
            # TODO: update new worker to RedisDB
            CH_WORKER_TO_BRAIN = context["ch_to_brain"]
            CH_BRAIN_TO_WORKER = context["ch_to_worker"]

            hshake_reply = {
                "verb": "hshake-2",
                "context": {
                    "workerID": context["workerID"]
                }
            }
            # TODO: the channel name should be modified
            await self._nats_cli.publish(CH_BRAIN_TO_WORKER, str(hshake_reply).encode())
            # TODO(Ray): check the channel have been subscribed or not?
            # should not be double subscribed
            await self._nats_cli.subscribe(CH_WORKER_TO_BRAIN, cb=self._private_worker_handler)

    async def _api_handler(self, recv):
        """asychronous handler for listen cmd from api server

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                mst (msg): message
        """
        ch = recv.subject
        reply = recv.reply
        msg = msg_to_json(recv.data)

        logging.debug("Received in api_handler() '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))

        if msg['command'] == MESSAGES['ch_api_brain']['REQ_APPLICATION_STATUS']:
            # TODO: Return application status
            await self._nats_cli.publish(reply, str("It is running").encode())
        elif msg['command'] == MESSAGES['ch_api_brain']['START_APPLICATION']:
            job = {
                'id': msg['params']['camera']['id'],
                'action': 'create worker',
                'reply': reply
            }
            request = {
                'command': MESSAGES['ch_brain_res']['CREATE_WORKER'],
                'params': {
                    # TODO: For running multiple brain instances, the id
                    #       should combine with a brain id to create a
                    #       unique id across brains
                    'ticketId': job['id']
                }
            }
            pending_jobs[job['id']] = job
            await self._nats_cli.publish(CH_BRAIN_TO_RES, str(request).encode())
        elif msg['command'] == MESSAGES['ch_api_brain']['STOP_APPLICATION']:
            # TODO: Stop application
            await self._nats_cli.publish(reply, str("It is stoping").encode())
        else:
            logging.error("Undefined command: {}".format(msg['command']))

    async def _res_handler(self, recv):
        """asychronous handler for listen response from resource manager

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                mst (msg): message
        """
        msg = msg_to_json(recv.data)
        if msg['command'] == MESSAGES['ch_brain_res']['CREATE_WORKER']:
            worker_id = msg['response']['workerId']
            job = pending_jobs[msg['response']['ticketId']]
            del pending_jobs[msg['response']['ticketId']]
            logging.info('Creating worker, ID = {}'.format(worker_id))
            await self._nats_cli.publish(job['reply'], str("OK").encode())

    def start(self):
        self._main_loop.run_until_complete(self._setup())
        self._main_loop.run_forever()
        self._main_loop.close()

if __name__ == '__main__':
    brain = Brain()
    brain.start()
