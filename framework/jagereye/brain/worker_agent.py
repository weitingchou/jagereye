import aioredis
import json, os, time
from jsonschema import Draft4Validator as Validator

from jagereye.util import logging
from jagereye.util import static_util
from jagereye.util.generic import get_func_name
from jagereye.brain.status_enum import WorkerStatus
from jagereye.brain.utils import jsonify


# create worker schema validator
with open(static_util.get_path('worker.json'), 'r') as f:
    validator = Validator(json.loads(f.read()))

class WorkerAgent(object):
    def __init__(self, typename, mem_db):
        self._typename = typename
        self._mem_db = mem_db

    def _get_anal_key(self, anal_id):
        return '{}:anal:{}'.format(self._typename, anal_id)

    def _get_worker_key(self, worker_id, field):
        # TODO(Ray): field only allow 'status', 'pipelines', 'hbeat', 'analyzerId'
        return '{}:worker:{}:{}'.format(self._typename, worker_id, field)

    async def get_worker_id(self, anal_id):
        """ check if the worker for the analyzer is existed

        Args:
            anal_id (string): analyzer id

        Returns:
            string: worker_id, and None for non-exist
        """
        key = 'anal:{}:workerId'.format(anal_id)
        result = await self._mem_db.get(key)
        if result:
            return result
        else:
            return None

    async def create_analyzer(self, anal_id, worker_id):
        """Create a initial analyzer record

        Args:
            anal_id (string): analyzer id
            worker_id (string): worker id
        Returns:
            bool: True for success, False otherwise
        """
        # set 'workerId' field in analyzer table
        await self._mem_db.set(self._get_anal_key(anal_id), worker_id)

        # set 'status', 'pipelines', 'analyzerId' fields in worker table
        await self._mem_db.set(self._get_worker_key(worker_id, 'status'), WorkerStatus.INITIAL.name)
        await self._mem_db.set(self._get_worker_key(worker_id, 'pipelines'), str([]))
        await self._mem_db.set(self._get_worker_key(worker_id, 'analyzerId'), anal_id)

        # TODO(Ray): error handler: what if set failed?
        return True

    async def get_status(self, anal_id=None, worker_id=None):
        # TODO(Ray): should prohibit call get_status with both anal_id and worker_id?
        key = None
        if worker_id:
            key = self._get_worker_key(worker_id, 'status')
        elif anal_id:
            # get worker_id by anal_id
            worker_id = await self._mem_db.get(self._get_anal_key(anal_id))
            # TODO(Ray): if worker_id not exist, error handler
            if not worker_id:
                return None
            key = self._get_worker_key(worker_id, 'status')
        else:
            return None
        return (await self._mem_db.get(key)).decode()

    async def update_status(self, status, anal_id=None, worker_id=None):
        # TODO(Ray): should prohibit call get_status with both anal_id and worker_id?
        key = None
        if worker_id:
            key = self._get_worker_key(worker_id, 'status')
        elif anal_id:
            # get worker_id by anal_id
            worker_id = await self._mem_db.get(self._get_anal_key(anal_id))
            # TODO(Ray): if worker_id not exist, error handler
            if not worker_id:
                return None
            key = self._get_worker_key(worker_id, 'status')
        else:
            return None
        return (await self._mem_db.set(key, status))

    async def update_pipelines(self, pipelines, worker_id):
        # TODO(Ray): should prohibit call get_status with both anal_id and worker_id?
        key = None
        if not worker_id:
            return
        key = self._get_worker_key(worker_id, 'pipelines')
        return (await self._mem_db.set(key, str(pipelines)))

    async def get_anal_id(self, worker_id):
        """Get analyzer ID by worker ID.

        Args:
            worker_id (string): worker id

        Returns:
            string: analyzer id
        """
        key = self._get_worker_key(worker_id, 'analyzerId')
        return (await self._mem_db.get(key)).decode()

    async def update_hbeat(self, worker_id):
        """Update last heartbeat for the worker with worker id.

        Args:
            worker_id (string): worker id

        Returns:
            bool: True for success, False otherwise
        """
        timestamp = time.time()
        key = self._get_worker_key(worker_id, 'hbeat')
        return (await self._mem_db.execute('set', key, timestamp, 'xx'))

    async def start_listen_hbeat(self, worker_id):
        """make brain start to listen heartbeat from worker with worker_id.

        Args:
            worker_id (string): worker id

        Returns:
            bool: True for success, False otherwise
        """
        timestamp = time.time()
        key = self._get_worker_key(worker_id, 'hbeat')
        return (await self._mem_db.set(key, timestamp))


    async def examine_all_workers(self, threshold):
        """Examine if each workers is alive

        """
        # extract all worker's status
        status_search_key = self._get_worker_key('*', 'status')
        status_keys = await self._mem_db.keys(status_search_key)
        if not status_keys:
           return
        status_values = await self._mem_db.execute('mget', *status_keys)
        qualified_status_keys = []
        qualified_hbeat_keys = []
        for status_key, status in zip(status_keys, status_values):
            status = status.decode()
            if (status == WorkerStatus.READY.name) or (status == WorkerStatus.RUNNING.name):
                qualified_status_keys.append(status_key)
                qualified_hbeat_keys.append(status_key.replace(b'status', b'hbeat'))
        if not qualified_status_keys:
            return
        status_values = await self._mem_db.execute('mget', *qualified_status_keys)
        hbeat_values = await self._mem_db.execute('mget', *qualified_hbeat_keys)
        timestamp = time.time()

        for status_key, status, hbeat in zip(qualified_status_keys, status_values, hbeat_values):
            hbeat = float(hbeat.decode())
            if (timestamp - hbeat) > float(threshold):
                logging.debug('worker {} is down'.format(status_key.decode().replace(':status', '')))
                # change the staus to DOWN
                #TODO(Ray): error handler
                print(status_key)
                await self._mem_db.set(status_key, WorkerStatus.DOWN.name)
