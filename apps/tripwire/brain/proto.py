import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
import json

import ast

import time

CHANNEL_NAME = "ch_api_brain"
CH_HEARTBEAT = "ch_heartbeat"

# channel for worker handshake
CH_WORKER = "ch_brain"

# memory db, it will be replace to redis
CH_WORKER_TO_BRAIN = ""
CH_BRAIN_TO_WORKER = ""

#def create_cam_exec(data):
#    i = 0
#    while(i<10000000):
#        if i%200000 == 0:
#            print(str(i)+"  "+str(data))
#        i = i+1
#def finish_cb(task):
#    res = task.result()
#    print(res)
#    print("finish!!!!")
#        
#
#async def api_handler(msg):
#    subject = msg.subject
#    reply = msg.reply
#    data = msg.data.decode()
#    print("Received a message on '{subject} {reply}': {data}".format(subject=subject, reply=reply, data=data))
#    
#    data = ast.literal_eval(data)
#
#    start = time.time()
#    data["start"] = start
#    create_cam = loop.run_in_executor(None, create_cam_exec, data)
#    create_cam.add_done_callback(finish_cb)
#
#


async def hb_handler(msg):
    subject = msg.subject
    reply = msg.reply
    data = msg.data.decode()
    print("Received a hb on '{subject} {reply}': {data}".format(subject=subject, reply=reply, data=data))


async def run(loop):
    nc = NATS()

    await nc.connect(io_loop=loop)

    async def worker_handler(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        print("Received a event on '{subject} {reply}': {data}".format(subject=subject, reply=reply, data=data))

    async def hshake_handler(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        hshake_req = json.loads(data.replace("'", '"'))
        print("Received a hshake on '{subject} {reply}': {data}".format(subject=subject, reply=reply, data=hshake_req))
        print("start to handshake-back")
        
        CH_WORKER_TO_BRAIN = hshake_req["context"]["ch_to_brain"]
        CH_BRAIN_TO_WORKER = hshake_req["context"]["ch_to_worker"]

        await nc.publish(CH_BRAIN_TO_WORKER, b"I am brain")
        await nc.subscribe(CH_WORKER_TO_BRAIN, cb=worker_handler)

    # await nc.subscribe(CHANNEL_NAME, cb=api_handler)
    await nc.subscribe(CH_HEARTBEAT, cb=hb_handler)
    await nc.subscribe(CH_WORKER, cb=hshake_handler)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    loop.run_forever()
    loop.close()
