import asyncio
import aioredis
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
from pymongo import MongoClient
import time

from jagereye.util import logging
from jagereye.util.generic import get_func_name

from jagereye.brain.utils import jsonify, jsondumps
from jagereye.brain import ticket
from jagereye.brain.event_agent import EventAgent

from jagereye.brain.status_enum import WorkerStatus
from jagereye.brain.contract import API, InvalidRequestType, InvalidRequestFormat

# TODO(Ray): must merge to the STATUS enum in jagereye/worker/worker.py
# Loading messaging
with open('../../../services/messaging.json', 'r') as f:
    MESSAGES = jsonify(f.read())

# NATS channels
CH_API_TO_BRAIN = "ch_api_brain"
CH_PUBLIC_BRAIN = "ch_brain"

CH_BRAIN_TO_RES = "ch_brain_res"
CH_RES_TO_BRAIN = "ch_res_brain"

class Brain(object):
    """Brain the base class for brain service.

    It provides basic interactions to api-server, workers, resource-mgr.
    Like handshake to workers.

    Attributes:

    """
    def __init__(self, typename, ch_public='public_brain',
                mq_host='nats://localhost:4222',
                mem_db_host='redis://localhost:6379',
                db_host='mongodb://localhost:27017'):

        """initial the brain service

        Args:
            ch_public (str): the public nats channel for listening all workers
            mq_host (str): the host and port of nats server
        """
        self._typename = typename
        self._API = API(self._typename)
        self._main_loop = asyncio.get_event_loop()
        # TODO(Ray): check NATS is connected to server, error handler
        # TODO(Ray): check mq_host is valid
        # TODO(Ray): _nats_cli should be abstracted as _mq_cli
        self._mq_host = mq_host
        self._nats_cli = NATS()
        self._ch_public = ch_public
        
        self._ticket = None
        self._event_agent = None

        self._mem_db_cli = None
        self._mem_db_host = mem_db_host

        # TODO(Ray): db api need to be abstracted,
        # TODO(Ray): and the MongoClient is Sync, need to be replaced to async version
        self._db_host = db_host
        db_cli = MongoClient(self._db_host)
        self._event_db = db_cli.event

    async def _setup(self):
        """register all handler

        """
        # TODO(Ray): both are mem db operations, need to be abstracted, or redesign
        self._mem_db_cli = await aioredis.create_redis(self._mem_db_host, loop=self._main_loop)
        self._ticket = await ticket.create_ticket(self._main_loop)
        self._event_agent = EventAgent(self._typename, self._mem_db_cli, self._event_db)

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
                msg (binary str): request message
        """
        ch = recv.subject
        reply = recv.reply
        msg = jsonify(recv.data)
        try:
            verb = msg['verb']
            context = msg['context']
        except Exception as e:
            logging.error('Exception in {}, type: {} error: {}'.format(get_func_name(), type(e), e))
        else:
            if verb == 'hshake-3':
                logging.debug('Received "hshake-3" in {func}: "{subject} {reply}": {data}'.\
                    format(func=get_func_name(), subject=ch, reply=reply, data=msg))
                logging.debug('finish handshake')

                # change worker status in DB
                # TODO(Ray): check 'anal_worker_id' in context, error handler
                anal_worker_id = context['anal_worker_id']
                analyzer_id = anal_worker_id.split(':')[1]
                # check worker status is HSHAKE-1?
                worker_obj = jsonify(await self._mem_db_cli.get(anal_worker_id))
                if worker_obj['status'] == WorkerStatus.HSHAKE_1.name:
                    # update worker status to READY

                    worker_obj['status'] = WorkerStatus.READY.name
                    # TODO(Ray): error handler for redis result
                    await self._mem_db_cli.set(anal_worker_id, str(worker_obj))

                    # check if there is a ticket for the analyzer
                    result = await self._ticket.get(analyzer_id)
                    if result:
                        # assign job to worker
                        context['ticket'] = result
                        context['ticket']['ticket_id'] = analyzer_id
                        config_req = {
                            'verb': 'config',
                            'context': context
                        }
                        # update worker status to CONFIG
                        worker_obj['status'] = WorkerStatus.CONFIG.name
                        await self._mem_db_cli.set(anal_worker_id, str(worker_obj))
                        await self._nats_cli.publish(context['ch_to_worker'], str(config_req).encode())
                    else:
                        # no ticket for the analyzer
                        logging.debug('Receive "hshake3" in {}: no ticket for analyzer {}'.\
                                format(get_func_name(), analyzer_id))
                else:
                    logging.error('Receive "hshake1" in {}: with unexpected worker status "{}"'.\
                            format(get_func_name(), worker_obj['status']))
            elif verb == 'config_ok':
                logging.debug('Received "config_ok" in {func}: "{subject} {reply}": {data}'.\
                    format(func=get_func_name(), subject=ch, reply=reply, data=msg))
                anal_worker_id = context['anal_worker_id']
                ticket_id = context['ticket']['ticket_id']
                worker_obj = jsonify(await self._mem_db_cli.get(anal_worker_id))
                # check if  worker status is 'CONFIG'
                if worker_obj['status'] == WorkerStatus.CONFIG.name:
                    worker_obj['status'] = WorkerStatus.RUNNING.name
                    # update the status to RUNNING
                    await self._mem_db_cli.set(anal_worker_id, str(worker_obj))
                    # delete ticket
                    await self._ticket.delete(ticket_id)
                else:
                    # TODO(Ray): when status not correct, what to do?
                    logging.error('Receive "config_ok" in {}, but the worker status is {}'.\
                            format(get_func_name, worker_obj['status']))
            elif verb == 'event':
                worker_id = context['workerID']

                # TODO(Ray): worker table operation abstraction
                anal_worker_id = await self._mem_db_cli.keys('anal_worker:*:{}'.format(worker_id))
                anal_worker_id = str(anal_worker_id[0])
                # retrieve analyzer_id
                analyzer_id = anal_worker_id.split(':')[1]

                logging.debug('Receive event inform in {}.'.format(get_func_name()))

                # consume events from the worker
                events = await self._event_agent.consume_from_worker(worker_id)
                if not events:
                    return

                self._event_agent.store_in_db(events, analyzer_id)

                logging.debug('Events: "{}" from worker "{}"'.format(events, worker_id))

                # TODO: Send events back to notification service.
            elif verb == 'hbeat':
                # TODO: need to update to DB
                logging.debug('hbeat: {}'.format(str(msg)))

    async def _public_brain_handler(self, recv):
        """asychronous handler for public channel all initial workers

        listen to the public channel,
        which is for a worker registers to brain when the worker initializing

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                msg (binary str): request message
        """
        ch = recv.subject
        reply = recv.reply
        msg = jsonify(recv.data)

        try:
            verb = msg['verb']
            context = msg['context']
        except Exception as e:
            logging.error('Exception in {}, type: {} error: {}'.format(get_func_name(), type(e), e))
        else:
            if verb == 'hshake-1':
                logging.debug('Received "hshake-1" msg in {func}: "{subject}": {data}'.\
                        format(func=get_func_name(), subject=ch, reply=reply, data=msg))
                try:
                    worker_id = context['workerID']
                    # TODO(Ray): the channel name would be convention or just recv from worker?
                    ch_worker_to_brain = context['ch_to_brain']
                    ch_brain_to_worker = context['ch_to_worker']
                except Exception as e:
                    logging.error('Exception in {}, type: {} error: {}'.format(get_func_name(), type(e), e))
                else:
                    # get worker_obj
                    # TODO(Ray): check 'result', error handler
                    result = await self._mem_db_cli.keys('anal_worker:*:{}'.format(worker_id))
                    anal_worker_id = (result[0]).decode()

                    # check worker status is INITIAL?
                    worker_obj = jsonify(await self._mem_db_cli.get(anal_worker_id))
                    if worker_obj['status'] == WorkerStatus.INITIAL.name:
                        # update worker status
                        worker_obj['status'] = WorkerStatus.HSHAKE_1.name
                        # TODO(Ray): error handler for redis result
                        await self._mem_db_cli.set(anal_worker_id, str(worker_obj))

                        context['anal_worker_id'] = anal_worker_id
                        hshake_reply = {
                            'verb': 'hshake-2',
                            'context': context
                        }
                        await self._nats_cli.publish(ch_brain_to_worker, str(hshake_reply).encode())
                        await self._nats_cli.subscribe(ch_worker_to_brain, cb=self._private_worker_handler)

                    else:
                        logging.error('Receive "hshake1" in {}: with unexpected worker status "{}"'.\
                                format(get_func_name(), worker_obj['status']))


    async def _api_handler(self, recv):
        """asychronous handler for listen cmd from api server

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                msg (binary str): request message
        """
        ch = recv.subject
        reply = recv.reply
        msg = jsonify(recv.data)
        timestamp = round(time.time())

        logging.debug('Received in api_handler() "{subject} {reply}": {data}'.\
                 format(subject=ch, reply=reply, data=msg))

        try:
            self._API.validate(msg)
        except InvalidRequestFormat:
            logging.error('Exception in {}: invalid request format from api'.format(get_func_name()))
            return
        except InvalidRequestType:
            # ignore the exception since the request is not for us
            return

        analyzer_id = msg['params']['id']

        if msg['command'] == MESSAGES['ch_api_brain']['REQ_ANALYZER_STATUS']:
            # TODO: Return application status
            await self._nats_cli.publish(reply, str("It is running").encode())

        elif msg['command'] == MESSAGES['ch_api_brain']['START_ANALYZER']:
            context = {'msg': msg, 'reply': reply, 'timestamp': timestamp}
            if await self._ticket.set(analyzer_id, context) == 0:
                # ticket already exists for analyzer #id, reject the request
                # because we allow only one ticket for one write operation of the
                # same analyzer at the same time
                return await self._nats_cli.publish(reply, jsondumps(self._API.reply_not_aval()).encode())

            # check if worker for the analyzer #id exists?
            # if yes, just re-config worker
            # if no, request resource manager for launching a worker
            worker_res = await self._mem_db_cli.keys('anal_worker:{}:*'.format(analyzer_id))
            if worker_res:
                # TODO(Ray): if yes, just re-config worker
                logging.debug('worker exists, re-configure it')
            else:
                # no worker, request resource manager for launching a new worker

                worker_state = WorkerStatus.CREATE.name

                # create an placeholder entry in worker table
                anal_worker_id = 'anal_worker:{}:placeholder'.format(analyzer_id)
                worker_obj = {
                    'status': worker_state,
                    'last_hbeat': timestamp,
                    'pipelines': []
                }
                await self._mem_db_cli.set(anal_worker_id, str(worker_obj))
                logging.debug('Create a worker "placeholder" for analyzer "{}"'.format(analyzer_id))

                # reply back to api_server
                status_obj = { 'result': self._API.anal_status_obj(worker_state) }
                await self._nats_cli.publish(reply, jsondumps(status_obj).encode())

                # request resource manager to launch a worker
                req = {
                    'command': MESSAGES['ch_brain_res']['CREATE_WORKER'],
                    'ticketId': ticket_id,
                    'params': {
                        # TODO: For running multiple brain instances, the id
                        #       should combine with a brain id to create a
                        #       unique id across brains
                        'workerName': 'jagereye/worker_tripwire'
                    }
                }
                await self._nats_cli.publish(CH_BRAIN_TO_RES, str(req).encode())

        elif msg['command'] == MESSAGES['ch_api_brain']['STOP_ANALYZER']:
            # TODO: Stop application
            context = {'msg': msg, 'reply': reply, 'timestamp': timestamp}
            if await self._ticket.set(analyzer_id, context) == 0:
                # ticket already exists for analyzer #id, reject the request
                # because we allow only one ticket for one write operation of the
                # same analyzer at the same time
                return await self._nats_cli.publish(reply, jsondumps(self._API.reply_not_aval()).encode())

            await self._nats_cli.publish(reply, str("It is stoping").encode())

        else:
            logging.error('Undefined command: {}'.format(msg['command']))

    async def _res_handler(self, recv):
        """asychronous handler for listen response from resource manager

        Args:
            recv (:obj:`str`): include 'subject', 'reply', 'msg'
                subject (str): the src channel name
                reply (str): the reply channel name
                msg (binary str): message
        """
        msg = jsonify(recv.data)

        # Check has error or not.
        if 'error' in msg:
            # TODO(JiaKuan Su): Error handling.
            logging.error('Error code: "{}" from resource manager'
                          .format(msg['error']['code']))
            return

        if msg['command'] == MESSAGES['ch_brain_res']['CREATE_WORKER']:
            # whenver the resource manager create a worker for the brain
            # then inform to brain
            worker_id = msg['response']['workerId']
            analyzer_id = msg['ticketId']   # we use analyzer ID as ticket ID

            logging.info('Launch worker "{}" for analyzer "{}"'.format(worker_id, analyzer_id))

            # update the anal_worker record:
            # retrieve the original anal_worker record
            # TODO(Ray): confirm that the result must have 1 element
            ori_id = 'anal_worker:{}:placeholder'.format(analyzer_id)
            worker_obj = jsonify(await self._mem_db_cli.get(ori_id))
            anal_worker_id = 'anal_worker:{}:{}'.format(analyzer_id, worker_id)
            # change status
            worker_obj['status'] = WorkerStatus.INITIAL.name

            # append a new anal_worker record with worker_id
            await self._mem_db_cli.set(anal_worker_id, str(worker_obj))

            # delete the original record
            await self._mem_db_cli.delete(ori_id)

    def start(self):
        self._main_loop.run_until_complete(self._setup())
        self._main_loop.run_forever()
        self._main_loop.close()
