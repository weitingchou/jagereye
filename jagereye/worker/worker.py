import asyncio
import aioredis
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
from concurrent.futures import ThreadPoolExecutor
import time
import json
from enum import Enum

from jagereye.worker.timer import Timer
from jagereye.util import logging

# public brain channel 
CH_BRAIN = "ch_brain"

STATUS = Enum("STATUS", "INITIAL HSHAKE_1 READY RUNNING")

class Worker(object):
    def __init__(self,
                 worker_id,
                 mq_host='nats://localhost:4222',
                 mem_db_host='redis://localhost:6379'):
        self._main_loop = asyncio.get_event_loop()
        
        # TODO(Ray): check NATS is connected to server, error handler
        # connect NATs server, default is nats://localhost:4222
        # TODO(Ray): check mq_host is valid
        self._nats_cli = NATS()
        self._mem_db_cli = None
        self._worker_id = worker_id
        self._ch_worker_to_brain = self._gen_ch_WtoB() 
        self._ch_brain_to_worker = self._gen_ch_BtoW()
        self._event_queue_key = 'event:brain:{}'.format(worker_id)
        self.pipeline = None
        self._status = STATUS.INITIAL
        # TODO(Ray): not sure _subscribes should exist
        self._subscribes = []
        self._mq_host = mq_host
        self._mem_db_host = mem_db_host
        # Create a limited thread pool.
        # _executor is to run main task like tensorflow
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def _setup(self):
        if self._status == STATUS.INITIAL:
            # Connect to memory database.
            self._mem_db_cli = await aioredis.create_redis(self._mem_db_host,
                                                           loop=self._main_loop)

            # TODO(Ray): need error handler for binding to an event loop
            await self._nats_cli.connect(io_loop=self._main_loop, servers=[self._mq_host])

            # start handshake to brain
            hshake_1_req = {
                "verb": "hshake-1",
                "context": {"workerID": self._worker_id,
                            "ch_to_brain": self._ch_worker_to_brain,
                            "ch_to_worker": self._ch_brain_to_worker
                    }
                }

            await self._nats_cli.subscribe(self._ch_brain_to_worker, cb=self._brain_handler)
            await self._nats_cli.publish(CH_BRAIN, str(hshake_1_req).encode())
            self._status = STATUS.HSHAKE_1
            logging.debug("start handshake, status: hshake-1")
        else:
            logging.debug("expect worker status be 'initial' when setup")

    async def _brain_handler(self, recv):
        ch = recv.subject
        reply = recv.reply
        # TODO(Ray): what if json cannot load data, need check
        msg = recv.data.decode()
        msg = json.loads(msg.replace("'", '"'))
        verb = msg["verb"]
        context = msg["context"]

        if (verb == "hshake-2") and (self._status == STATUS.HSHAKE_1):
            logging.debug("Received 'hshake-2' msg in _brain_handler(): '{subject} {reply}': {data}".\
                    format(subject=ch, reply=reply, data=msg))
            if context["workerID"] == self._worker_id:
                hshake_3_req = {
                        "verb": "hshake-3",
                        "context": {
                                "workerID": self._worker_id
                            }
                        }
                self._status = STATUS.READY
                # finish handshake, so register heartbeater
                # trigger heartbeat in 2 sec interval
                hbeat_timer = Timer(2, self._hbeat_publisher)
                await self._nats_cli.publish(self._ch_worker_to_brain, str(hshake_3_req).encode())

        if (verb == "assign") and (self._status == STATUS.READY):
            logging.debug("Received 'assign' msg in _brain_handler(): '{subject} {reply}': {data}".\
                    format(subject=ch, reply=reply, data=msg))
            if context["workerID"] == self._worker_id:
                # TODO(Ray): check pipeline existed,
                # but it has check in register_pipeline()
                # use the thread pool to run object detect
                self._main_loop.run_in_executor(self._executor, self.pipeline)

    
    def send_event(self, name, context):
        """Send an new event to brain.

        Args:
          name (string): The event name.
          context (dict): The event context.
        """
        logging.debug('Try to send event (name = "{}", context = "{}") to brain'
                      .format(name, context))

        # Construct the key of event queue.
        event_queue_key = 'event:brain:{}'.format(self._worker_id)
        # Construct the event.
        event = {
            'name': name,
            'context': context
        }
        # Construct the request to publish.
        request = {
            'verb': 'event',
            'context': {
                'workerID': self._worker_id
            }
        }
        # Store the event in memory database.
        self._mem_db_cli.rpush(event_queue_key, str(event))
        # publish the request to brain.
        async_publish = self._nats_cli.publish(self._ch_worker_to_brain,
                                               str(request).encode())
        asyncio.run_coroutine_threadsafe(async_publish, self._main_loop)

        logging.debug('Success to send event (name = "{}", context = "{}") to '
                      'brain'.format(name, context))

    async def _hbeat_publisher(self):
        timestamp = time.time()
        hbeat_req = {
                "verb": "hbeat",
                "context": {
                        "workerID": self._worker_id,
                        "timestamp": timestamp
                    }
                }
        # TODO(Ray) check self._ch_worker_to_brain exist?
        await self._nats_cli.publish(self._ch_worker_to_brain, str(hbeat_req).encode())

    def register_pipeline(self, pipeline):
        logging.debug("register pipeline in register_pipeline()")
        # check if the pipeline is function or not
        if not callable(pipeline):
            logging.error("wrong type of pipeline in register_pipeline()")

        self.pipeline = pipeline

    def _gen_ch_WtoB(self):
        return "ch_"+str(self._worker_id)+"_brain"

    def _gen_ch_BtoW(self):
        return "ch_brain_"+str(self._worker_id)

    def start(self):
        self._main_loop.run_until_complete(self._setup())
        self._main_loop.run_forever()

