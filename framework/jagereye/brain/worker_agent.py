import aioredis
import json, os, time
from jsonschema import Draft4Validator as Validator

from jagereye.util import logging
from jagereye.util.generic import get_func_name
from jagereye.brain.status_enum import WorkerStatus
from jagereye.brain.utils import jsonify


# create a schema validator with a json file
cuurent_path = os.path.dirname(__file__)
schema_path = os.path.join(cuurent_path, 'schema/worker.json')
schema = json.load(open(schema_path))
validator = Validator(schema)

class WorkerAgent(object):
    def __init__(self, typename, mem_db):
        self._typename = typename
        self._mem_db = mem_db

    async def is_existed(self, analyzer_id):
        """ check if the worker for the analyzer is existed

        Args:
            analyzer_id (string): analyzer id

        Returns:
            bool: True for exist, False for non-exist
        """
        worker_res = await self._mem_db.keys('anal_worker:{}:*'.format(analyzer_id))
        if worker_res:
            return True
        else:
            return False

    async def create_worker(self, analyzer_id):
        """Create a initial worker record

        Args:
            analyzer_id (string): analyzer id

        Returns:
            bool: True for success, False otherwise
        """

        worker_state = WorkerStatus.CREATE.name
        # create an placeholder entry in worker table
        anal_worker_id = 'anal_worker:{}:placeholder'.format(analyzer_id)
        timestamp = round(time.time())
        worker_info = {
            'status': worker_state,
            'last_hbeat': timestamp,
            'pipelines': []
        }
        return (await self._mem_db.set(anal_worker_id, str(worker_info)))

    async def get_info(self, worker_id=None, analyzer_id=None):
        """Get worker info by worker id

        Args:
            analyzer_id (string): analyzer_id
            worker_id (string): worker id

        Returns:
            dict: worker information
        """
        anal_worker_id = None
        if (worker_id and analyzer_id):
            anal_worker_id = 'anal_worker:{}:{}'.format(analyzer_id, worker_id)
        elif worker_id:
            # TODO(Ray): check 'result', error handler
            result = await self._mem_db.keys('anal_worker:*:{}'.format(worker_id))
            anal_worker_id = (result[0]).decode()
            analyzer_id = anal_worker_id.split(':')[1]
        elif analyzer_id:
            # TODO(Ray): check 'result', error handler
            result = await self._mem_db.keys('anal_worker:{}:*'.format(analyzer_id))
            anal_worker_id = (result[0]).decode()
            worker_id = anal_worker_id.split(':')[2]
        else:
            # TODO(Ray): if both worker_id and analyzer_id are implicit false (like None, empty str, [], {})
            #           ,need error handler
            return None
        worker_obj = jsonify(await self._mem_db.get(anal_worker_id))
        if worker_obj:
            worker_obj['analyzer_id'] = analyzer_id
            worker_obj['worker_id'] = worker_id
            return worker_obj
        else:
            return None

    async def get_anal_id(self, worker_id):
        """Get analyzer ID by worker ID.

        Args:
            worker_id (string): worker id

        Returns:
            string: analyzer id
        """
        result = await self._mem_db.keys('anal_worker:*:{}'.format(worker_id))
        anal_worker_id = (result[0]).decode()
        # retrieve analyzer_id
        analyzer_id = anal_worker_id.split(':')[1]
        return analyzer_id

    async def update_status(self, worker_id, status):
        """Update status for worker with the worker id.

        Args:
            worker_id (string): worker id
            status (string): The new worker status.
                The status should be 'create', 'initial', 'hshake_1', 'config', 'ready' or 'running'.

        Returns:
            bool: True for success, False otherwise
        """
        result = await self._mem_db.keys('anal_worker:*:{}'.format(worker_id))
        # TODO(Ray): what if no anal_worker_id
        anal_worker_id = result[0]
        worker_obj = jsonify(await self._mem_db.get(anal_worker_id))
        worker_obj['status'] = status
        return (await self._mem_db.set(anal_worker_id, str(worker_obj)))

    async def update_last_hbeat(self, worker_id):
        """Update last heartbeat for the worker with worker id.

        Args:
            worker_id (string): worker id

        Returns:
            bool: True for success, False otherwise
        """
        # TODO(Ray)
        pass

    async def update_worker_id(self, analyzer_id, worker_id):
        """Update the worker id to the worker record

        Args:
            analyzer_id (string): analyzer id
            worker_id (string): worker id

        Returns:
            bool: True for success, False otherwise
        """
        # update the anal_worker record:
        # retrieve the original anal_worker record
        # TODO(Ray): confirm that the result must have 1 element
        ori_id = 'anal_worker:{}:placeholder'.format(analyzer_id)
        worker_obj = jsonify(await self._mem_db.get(ori_id))
        anal_worker_id = 'anal_worker:{}:{}'.format(analyzer_id, worker_id)

        # append a new anal_worker record with worker_id
        await self._mem_db.set(anal_worker_id, str(worker_obj))
        # delete the original record
        await self._mem_db.delete(ori_id)

