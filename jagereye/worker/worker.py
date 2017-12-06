import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
from concurrent.futures import ThreadPoolExecutor
import time
import json

from jagereye.worker.timer import Timer

import threading 

# public brain channel 
CH_BRAIN = "ch_brain"

class Worker(object):
    def __init__(self, mq_host):
        self._main_loop = asyncio.get_event_loop()
        
        # TODO: check NATS is connected to server, error handler
        # connect NATs server, default is nats://localhost:4222
        # TODO: check mq_host is valid
        self._nats_cli = NATS()
        self._worker_id = self._gen_worker_id()
        self._ch_worker_to_brain = self._gen_ch_WtoB() 
        self._ch_brain_to_worker = self._gen_ch_BtoW()
        self.pipeline = None
        # TODO: self._status = "initial"
        self._subscribes = []
        self._mq_host = mq_host
    async def _setup(self):
        # TODO: need error handler
        # bind to an event loop
        await self._nats_cli.connect(io_loop=self._main_loop, servers=[self._mq_host])


        # start handshake to brain
        hshake_1_req = { 
            "verb": "hshake-1",
            "context": {"workerID": self._worker_id,
                        "ch_to_brain": self._ch_worker_to_brain,
                        "ch_to_worker": self._ch_brain_to_worker
                }
            }

        # TODO: replace to add_done_callback()
        await self._nats_cli.subscribe(self._ch_brain_to_worker, cb=self._brain_handler)
        # TODO: maybe need a timeout
        await self._nats_cli.publish(CH_BRAIN, str(hshake_1_req).encode())

    async def _brain_handler(self, recv):
        # TODO: need a debug mode, logging
        print("in _hshake_2")     
        ch = recv.subject
        # TODO: what if json cannot load data
        msg = recv.data.decode()
        msg = json.loads(msg.replace("'", '"'))

        verb = msg["verb"]
        context = msg["context"]

        # check the reply
        if verb == "hshake-2":
            if context["workerID"] == self._worker_id:
                hshake_3_req = {
                        "verb": "hshake-3",
                        "context": {
                                "workerID": self._worker_id
                            }
                        }
                await self._nats_cli.publish(self._ch_worker_to_brain, str(hshake_3_req).encode())

                # finish handshake, so:
                # 1.register heartbeater 
                # 2 start the pipeline

                # trigger heartbeat in 2 sec interval
                hbeat_timer = Timer(2, self._hbeat_publisher)

                # TODO: check pipeline existed
                # Create a limited thread pool.
                executor = ThreadPoolExecutor(max_workers=1)
                # use the thread pool to run object detect
                self._main_loop.run_in_executor(executor, self.pipeline)

    
    def alert_to_brain(self, msg):
        # TODO: logging
        # print("alert!!")
        alert_req = {
                    "verb": "alert",
                    "context": {
                            "msg": msg
                        }
                }
        async_alert = self._nats_cli.publish(self._ch_worker_to_brain, str(alert_req).encode())
        asyncio.run_coroutine_threadsafe(async_alert, self._main_loop)

    async def _hbeat_publisher(self):
        timestamp = time.time()
        hbeat_req = {
                "verb": "hbeat",
                "context": {
                        "workerID": self._worker_id,
                        "timestamp": timestamp
                    }
                }
        # TODO check self._ch_worker_to_brain exist?
        await self._nats_cli.publish(self._ch_worker_to_brain, str(hbeat_req).encode())
        # TODO: print(threading.current_thread())

    def register_pipeline(self, pipeline):
        print("reg pipeline")
        self.pipeline = pipeline

    def _gen_ch_WtoB(self):
        return "ch_"+str(self._worker_id)+"_brain"

    def _gen_ch_BtoW(self):
        return "ch_brain_"+str(self._worker_id)

    def _gen_worker_id(self):
        return "worker_9527"

    def start(self):
        self._main_loop.run_until_complete(self._setup())
        self._main_loop.run_forever()

