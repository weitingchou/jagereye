import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
import json

import ast

import time

CH_API_TO_BRAIN = "ch_api_brain"

# channel for worker handshake
CH_PUBLIC_BRAIN = "ch_brain"

# memory db, it will be replace to redis
CH_WORKER_TO_BRAIN = ""
CH_BRAIN_TO_WORKER = ""

async def run(loop):
    nc = NATS()
    await nc.connect(io_loop=loop)

    async def private_worker_handler(recv):
        ch = recv.subject
        reply = recv.reply
        msg = recv.data.decode()
        # TODO: what if json cannot loads?
        msg = json.loads(msg.replace("'", '"'))
        # TODO: check the receive msg
        # and change the status of the worker
        verb = msg["verb"]
        context = msg["context"]

        print("Received in private_brain_handler() '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))
        if verb == "hshake-3":
            # TODO: update the status of the worker
            print("finish handshake!!")
        if verb == "hbeat":
            print("hbeat!!: "+str(msg))

    async def public_brain_handler(recv):
        ch = recv.subject
        reply = recv.reply
        msg = recv.data.decode()
        # TODO: what if json cannot loads?
        msg = json.loads(msg.replace("'", '"'))
        # TODO: check the receive msg
        # and change the status of the worker
        
        verb = msg["verb"]
        context = msg["context"]

        print("Received in public_brain_handler() '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))
        
        if verb == "hshake-1":
            print("start to handshake-back")
         
            # TODO: check if context has the keys "ch_to..."
            CH_WORKER_TO_BRAIN = context["ch_to_brain"]
            CH_BRAIN_TO_WORKER = context["ch_to_worker"]

            hshake_reply = {
                "verb": "hshake-2",
                "context": {
                        "workerID": context["workerID"]
                    }
                }
            await nc.publish(CH_BRAIN_TO_WORKER, str(hshake_reply).encode())
            # TODO: check the channel have been subscribed or not?
            # should not be double subscribed
            await nc.subscribe(CH_WORKER_TO_BRAIN, cb=private_worker_handler) 

    def create_cam_exec(data):
        i = 0
        while(i<10000000):
            if i%200000 == 0:
                print(str(i)+"  "+str(data))
            i = i+1
    def finish_cb(task):
        res = task.result()
        print(res)
        print("finish!!!!")

    async def api_handler(recv):
        ch = recv.subject
        reply = recv.reply
        msg = recv.data.decode()
        # TODO: what if json cannot loads?
        msg = json.loads(msg.replace("'", '"'))
        # TODO: check the receive msg
        # and change the status of the worker

        await nc.publish(reply, str("Im fine thank u").encode())
        print("Received in api_handler() '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))

        #start = time.time()
        #data["start"] = start
        #create_cam = loop.run_in_executor(None, create_cam_exec, data)
        #create_cam.add_done_callback(finish_cb)


    await nc.subscribe(CH_API_TO_BRAIN, cb=api_handler)
    await nc.subscribe(CH_PUBLIC_BRAIN, cb=public_brain_handler)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    loop.run_forever()
    loop.close()
