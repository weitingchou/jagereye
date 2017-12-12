import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
import json
from jagereye.util import logging

import ast

import time

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


async def run(loop, mq_host='nats://localhost:4222'):
    nc = NATS()
    await nc.connect(io_loop=loop, servers=[mq_host])

    async def private_worker_handler(recv):
        ch = recv.subject
        reply = recv.reply
        msg = recv.data.decode()
        # TODO(Ray): what if json cannot loads?
        msg = json.loads(msg.replace("'", '"'))
        # TODO(Ray): check the receive msg
        # and change the status of the worker
        verb = msg["verb"]
        context = msg["context"]

        logging.debug("Received in private_brain_handler(): '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))
        if verb == "hshake-3":
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
            await nc.publish("ch_brain_"+context["workerID"], str(assign_req).encode())

        if verb == "hbeat":
            logging.debug("hbeat: "+str(msg))

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

        logging.debug("Received in public_brain_handler(): '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))

        if verb == "hshake-1":
            logging.debug("start to handshake-back")

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
            # TODO(Ray): check the channel have been subscribed or not?
            # should not be double subscribed
            await nc.subscribe(CH_WORKER_TO_BRAIN, cb=private_worker_handler)

    async def api_handler(recv):
        ch = recv.subject
        reply = recv.reply
        msg = recv.data.decode()
        # TODO: what if json cannot loads?
        msg = json.loads(msg.replace("'", '"'))

        logging.debug("Received in api_handler() '{subject} {reply}': {data}".format(subject=ch, reply=reply, data=msg))

        if msg['command'] == MESSAGES['ch_api_brain']['REQ_APPLICATION_STATUS']:
            # TODO: Return application status
            await nc.publish(reply, str("It is running").encode())
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
            await nc.publish(CH_BRAIN_TO_RES, str(request).encode())
        elif msg['command'] == MESSAGES['ch_api_brain']['STOP_APPLICATION']:
            # TODO: Stop application
            await nc.publish(reply, str("It is stoping").encode())
        else:
            logging.error("Undefined command: {}".format(msg['command']))

    async def res_handler(recv):
        msg = recv.data.decode()
        msg = json.loads(msg.replace("'", '"'))

        if msg['command'] == MESSAGES['ch_brain_res']['CREATE_WORKER']:
            worker_id = msg['response']['workerId']
            job = pending_jobs[msg['response']['ticketId']]
            del pending_jobs[msg['response']['ticketId']]
            logging.info('Creating worker, ID = {}'.format(worker_id))
            await nc.publish(job['reply'], str("OK").encode())

    await nc.subscribe(CH_API_TO_BRAIN, cb=api_handler)
    await nc.subscribe(CH_PUBLIC_BRAIN, cb=public_brain_handler)
    await nc.subscribe(CH_RES_TO_BRAIN, cb=res_handler)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop, mq_host='nats://192.168.1.2:4222'))
    loop.run_forever()
    loop.close()
