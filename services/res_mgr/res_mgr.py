import json
import os
import subprocess
import uuid

import asyncio
from nats.aio.client import Client as NATS

from jagereye.util import logging


# Channels for worker and resource manager.
CH_BRAIN_TO_RES = 'ch_brain_res'
CH_RES_TO_BRAIN = 'ch_res_brain'


with open('../../services/messaging.json', 'r') as f:
    MESSAGES = json.loads(f.read())


async def run(loop, mq_host='nats://localhost:4222'):
    nc = NATS()
    await nc.connect(io_loop=loop, servers=[mq_host])

    # The list of active workers.
    worker_list = dict()

    def gen_worker_id():
        """Generate a unique worker ID.

        Returns:
          string: The unique worker ID.
        """
        return 'worker_{}'.format(uuid.uuid4())

    def create_worker(worker_id):
        """Create a worker instance.

        Args:
          worker_id (string): The worker ID.

        Returns:
          bool: True if worker is created successfully, False otherwise.
        """
        # TODO(JiaKuan Su): Create a docker container instead of just creating
        # a process.
        pwd = os.getcwd()
        os.chdir('../../apps/tripwire/worker')
        subprocess.Popen(['python3', 'worker.py', worker_id])
        os.chdir(pwd)

        # TODO(JiaKuan Su): Don't just return True.
        return True

    async def brain_handler(recv):
        msg = recv.data.decode()
        # TODO(JiaKuan Su): What if json cannot load?
        msg = json.loads(msg.replace("'", '"'))

        logging.info('Request from brain: {}'.format(msg))

        # Parse the command.
        command = msg['command']

        if command == MESSAGES[CH_BRAIN_TO_RES]['CREATE_WORKER']:
            ticket_id = msg['params']['ticketId']
            # Reply the created worker information to brain.
            worker_id = gen_worker_id()
            create_worker_reply = {
                'command': command,
                'response': {
                    'ticketId': ticket_id,
                    'workerId': worker_id
                }
            }

            logging.info('Response to brain: {}'.format(create_worker_reply))

            await nc.publish(CH_RES_TO_BRAIN, str(create_worker_reply).encode())


            # Create a worker.
            success = create_worker(worker_id)
            # Update the active worker list.
            # TODO(JiaKuan Su): Error handling.
            if success:
                worker_list[ticket_id] = {
                    'worker_id': worker_id,
                    'status': 'ACTIVE'
                }


    await nc.subscribe(CH_BRAIN_TO_RES, cb=brain_handler)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    loop.run_forever()
    loop.close()
