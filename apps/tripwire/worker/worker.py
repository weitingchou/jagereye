import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
from concurrent.futures import ThreadPoolExecutor
import time

import threading 

from timer import Timer

# channel for heartbeat
# CH_HEARTBEAT = "ch_heartbeat"

# channel for handshake to brain
CH_BRAIN = "ch_brain"


WORKER_ID = "worker_9527"


async def setup(loop):
    # TODO: check NATS is connected to server, error handler
    # connect NATs server, default is nats://localhost:4222
    nc = NATS()

    # TODO: error handler
    # bind to an event loop
    await nc.connect(io_loop=loop)
    
    async def alert_to_brain(msg):
        msg = "something happened!!!: "+str(msg)
        print(msg+"on => "+str(threading.current_thread())+'\n')
        await nc.publish("ch_"+WORKER_ID+"_brain", msg.encode())

    def run_tf():
        i = 0
        while True:
            if i%1000000 == 0:
                print(str(i/1000000)+"th step: "+str(threading.current_thread())+"\n" )
                loop.create_task(alert_to_brain(int(i/1000000)))
            i = i +1


    # heartbeat requestor 
    async def hbeat_requestor():
        timestamp = time.time()
        hbeat_req = {
                "workerID": WORKER_ID,
                "timestamp": timestamp
                }
        print("start heartbeat")
        await nc.publish(CH_HEARTBEAT, str(hbeat_req).encode())
        print("end heartbeat")
        print(threading.current_thread())
        print('\n')

    # start handshake
    # the private channel for this worker to brain
    CH_BRAIN_TO_WORKER = "ch_brain_"+WORKER_ID
    CH_WORKER_TO_BRAIN = "ch_"+WORKER_ID+"_brain"

    hshake_req = { 
            "verb": "handshake-1",
            "context": {"workerID": WORKER_ID,
                        "ch_to_brain": CH_WORKER_TO_BRAIN,
                        "ch_to_worker": CH_BRAIN_TO_WORKER
                }
            }
    
    async def worker_handler(msg):
        print("hi i am worker")
        print(msg.data.decode())
        await nc.publish(CH_WORKER_TO_BRAIN, "lets start".encode())
        # create a Timer with 2 sec interval, 
        # and register a heartbeat requestor on the Timer
        hbeat_timer = Timer(2, hbeat_requestor)
        # Create a limited thread pool.
        executor = ThreadPoolExecutor(max_workers=1)
        # use the thread pool to run object detect
        loop.run_in_executor(executor, run_tf)

    await nc.subscribe(CH_BRAIN_TO_WORKER, cb=worker_handler)
    await nc.publish(CH_BRAIN, str(hshake_req).encode())
    # finish handshake
#    yield from nc.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup(loop))
    loop.run_forever()
    loop.close()
