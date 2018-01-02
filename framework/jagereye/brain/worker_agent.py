import aioredis
import json
import os

from jsonschema import Draft4Validator as Validator
from jagereye.brain.utils import jsonify
from jagereye.util import logging


# create a schema validator with a json file
cuurent_path = os.path.dirname(__file__)
schema_path = os.path.join(cuurent_path, 'schema/worker.json')
schema = json.load(open(schema_path))
validator = Validator(schema)

class WorkerAgent(object):
    def __init__(self, typename, mem_db, db):
        self._typename = typename
        self._mem_db = mem_db

    await def create_worker(self, analyzer_id):
        """Create initially a worker record 

        create a worker record with $worker_id='placeholder' in mem_db 
        before get worker_id from resource manager;

        Args:
            analyzer_id (string): analyzer id

        Returns:
            bool: True for success, False otherwise
        """


    await def get_info_by_id(self, worker_id):
        """Get worker info by worker id

        Args:
            worker_id (string): worker id

        Returns:
            dict: worker information
        """

    await def get_info_by_anal_id(self, analyzer_id):
        """Get worker by analyzer id.

        Args:
            analyzer_id (string): analyzer id

        Returns:
            dict: worker information
        """

    await def get_anal_id(self, worker_id):
        """Get analyzer_id by worker_id.

        Args:
            worker_id (string): worker id

        Returns:
            string: analyzer id
        """

    await def update_status(self, worker_id, status):
        """Update status for worker with the worker id.

        Args:
            worker_id (string): worker id
            status (string): 'create', 'initial', 'hshake_1', 'config', 'ready', 'running'

        Returns:
            bool: True for success, False otherwise
        """

    await def update_last_hbeat(self, worker_id):
        """Update last heartbeat for the worker with worker id.

        Args:
            worker_id (string): worker id

        Returns:
            bool: True for success, False otherwise
        """

    async def update_worker_id(self, analyzer_id, worker_id):
        """Update the worker id to the worker record, replace the 'placeholder' 
        after brain receive the worker id from resource manager

        Args:
            analyzer_id (string): analyzer id
            worker_id (string): worker id

        Returns:
            bool: True for success, False otherwise
        """

