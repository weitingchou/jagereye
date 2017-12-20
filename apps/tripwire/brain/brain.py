import asyncio
import aioredis
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
import json

from jagereye.util import logging
import time
import uuid

from status_enum import WorkerStatus

# TODO(Ray): must merge to the STATUS enum in jagereye/worker/worker.py
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


def binary_to_json(binary_str):
    """convert binary string into json object

    Args:
        binary_str: binary string

    Returns:
        json object
    """

    # TODO(Ray): what if cannot decode()?
    string = binary_str.decode()
    # TODO(Ray): what if json cannot loads?
    return json.loads(string.replace("'", '"'))
    # TODO(Ray): check the receive msg

def gen_ticket_id(analyzer_id):
    """Generate a unique worker ID.

    Returns:
        string: The unique worker ID.
    """
    return 'ticket:' + analyzer_id + ':' + '{}'.format(uuid.uuid4())

class Brain(object):
    """Brain the base class for brain service.

    It provides basic interactions to api-server, workers, resource-mgr.
    Like handshake to workers.

    Attributes:

    """
    def __init__(self, ch_public="public_brain",
                mq_host='nats://localhost:4222',
                memDB_host='redis://localhost:6379'):

        """initial the brain service

        Args:
            ch_public (str): the public nats channel for listening all workers
            mq_host (str): the host and port of nats server
        """
        self._main_loop = asyncio.get_event_loop()
        # TODO(Ray): check NATS is connected to server, error handler
        # TODO(Ray): check mq_host is valid
        # TODO(Ray): _nats_cli should be abstracted as _mq_cli
        self._nats_cli = NATS()
        self._ch_public = ch_public
        self._memDB_cli = None
        self._mq_host = mq_host
        self._memDB_host = memDB_host

    async def _setup(self):
        """register all handler

        """
        self._memDB_cli = await aioredis.create_redis(self._memDB_host, loop=self._main_loop)

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
        msg = binary_to_json(recv.data)

        # and change the status of the worker
        verb = msg['verb']
        context = msg['context']

        if verb == 'hshake-3':
            logging.debug("Received 'hshake-3' in private_brain_handler(): '{subject} {reply}': {data}".\
                format(subject=ch, reply=reply, data=msg))

            logging.debug("finish handshake")
            # TODO(Ray): change worker status in DB
            # assign job to worker
            assign_req = {
                'verb': 'assign',
                'context': {
                    'workerID': context['workerID']
                }
            }
            # TODO(Ray): channel need to be get by search DB with workerID
            await self._nats_cli.publish('ch_brain_'+context['workerID'], str(assign_req).encode())
        elif verb == 'hbeat':
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
        msg = binary_to_json(recv.data)
        # TODO(Ray): check the receive msg
        # and change the status of the worker

        verb = msg['verb']
        context = msg['context']

        if verb == 'hshake-1':
            logging.debug("Received 'hshake-1' msg in _public_brain_handler(): '{subject} {reply}': {data}".\
                    format(subject=ch, reply=reply, data=msg))
            # TODO: check if context has the keys "ch_to..."
            # TODO: update new worker to RedisDB
            CH_WORKER_TO_BRAIN = context['ch_to_brain']
            CH_BRAIN_TO_WORKER = context['ch_to_worker']

            hshake_reply = {
                'verb': 'hshake-2',
                'context': {
                    'workerID': context['workerID']
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
        msg = binary_to_json(recv.data)

        logging.debug("Received in api_handler() '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))

        if msg['command'] == MESSAGES['ch_api_brain']['REQ_APPLICATION_STATUS']:
            # TODO: Return application status
            await self._nats_cli.publish(reply, str("It is running").encode())

        elif msg['command'] == MESSAGES['ch_api_brain']['START_APPLICATION']:
            # retrieve analyzer_id and apps
            # TODO(Ray): replace 'cam_id' 'camera'
            analyzer_id = msg['params']['camera']['id']
            # TODO(Ray): need to well define what's in 'apps'
            app = msg['params']['application']['name']

            # check if there is a ticket for analyzer?
            # if yes, reject the request from api
            # it no, continue
            ticket_res = await self._memDB_cli.keys('ticket:' + analyzer_id + ':*')
            if ticket_res:
                # TODO(Ray): if yes, reject the request from api
                logging.debug("if ticket exists, reject the request from api")
            else:
                # it no ticket for the analyzer

                # check the worker for the analyzer exists?
                # if yes, just re-config worker
                # if no, request resource manager for launching a worker
                worker_res = await self._memDB_cli.keys('anal_worker:' + analyzer_id + ':*')
                if worker_res:
                    # TODO(Ray): if yes, just re-config worker
                    logging.debug("if worker exists, just re-config worker")
                else:
                    # if no worker, request resource manager for launching a worker

                    # create a worker record & a ticket in memDB
                    timestamp = round(time.time())
                    ticket_id = gen_ticket_id(analyzer_id)
                    anal_worker_id = 'anal_worker:' + analyzer_id + ':placeholder'

                    # TODO: 'apps' need to re-define
                    ticket_obj = {
                        'apps': app,
                        'timestamp': timestamp
                    }
                    await self._memDB_cli.set( ticket_id , str(ticket_obj))

                    worker_obj = {
                        'status': WorkerStatus.CREATE.name,
                        'last_hbeat': timestamp,
                        'enabled_apps': []
                    }
                    logging.info('Create worker "placeholder" for analyzer "{}"'.format(analyzer_id))
                    await self._memDB_cli.set(anal_worker_id, str(worker_obj))

                    # reply back to api_server
                    await self._nats_cli.publish(reply, "OK".encode())

                    # request resource manager for launch a worker
                    req = {
                        'command': MESSAGES['ch_brain_res']['CREATE_WORKER'],
                        'params': {
                            # TODO: For running multiple brain instances, the id
                            #       should combine with a brain id to create a
                            #       unique id across brains
                            'ticketId': ticket_id
                        }
                    }
                    await self._nats_cli.publish(CH_BRAIN_TO_RES, str(req).encode())

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
        msg = binary_to_json(recv.data)
        if msg['command'] == MESSAGES['ch_brain_res']['CREATE_WORKER']:
            # whenver the resource manager create a worker for the brain
            # then inform to brain
            worker_id = msg['response']['workerId']
            ticket_id = msg['response']['ticketId']
            analyzer_id = ticket_id.split(':')[1]

            logging.info('Launch worker "{}" for analyzer "{}"'.format(worker_id, analyzer_id))

            # update the anal_worker record:
            # retrieve the original anal_worker record
            # TODO(Ray): confirm that the result must have 1 element
            ori_key = (await self._memDB_cli.keys('anal_worker:' + analyzer_id + ':*'))[0]
            worker_obj = binary_to_json(await self._memDB_cli.get(ori_key))
            anal_worker_id = 'anal_worker:' + analyzer_id + ':' +worker_id

            # change status
            worker_obj['status'] = WorkerStatus.INITIAL.name

            # append a new anal_worker record with worker_id
            await self._memDB_cli.set(anal_worker_id, str(worker_obj))

            # delete the original record
            await self._memDB_cli.delete(ori_key)


    def start(self):
        self._main_loop.run_until_complete(self._setup())
        self._main_loop.run_forever()
        self._main_loop.close()

if __name__ == '__main__':
    brain = Brain()
    brain.start()
