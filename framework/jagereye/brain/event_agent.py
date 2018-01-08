import aioredis
import json
import os

from jsonschema import Draft4Validator as Validator
from jagereye.brain.utils import jsonify
from jagereye.util import logging

# create a schema validator with a json file
current_path = os.path.dirname(__file__)
schema_path = os.path.join(current_path, 'schema/event.json')
schema = json.load(open(schema_path))
validator = Validator(schema)

class EventAgent(object):
    def __init__(self, typename, mem_db, db):
        self._typename = typename
        self._mem_db = mem_db
        self._db = db

    def store_in_db(self, events, analyzer_id):
        # validate
        valid_events = []
        for event in events:
            event['analyzer_id'] = analyzer_id
            if not validator.is_valid(event):
                logging.error('Fail validation for event {}'.format(event))
            else:
                valid_events.append(event)
        if valid_events:
            # TODO(Ray): error handler and logging if insert failed
            return self._db.insert_many(valid_events)
        else:
            return

    async def consume_from_worker(self, worker_id):
        """Get event array by worker ID.

        Args:
            worker_id (string): worker ID

        Returns:
            list of dict: an array of events from the worker
        """
        # Construct the key of event queue.
        event_queue_key = 'event:brain:{}'.format(worker_id)
        # Get the events.
        #TODO(Ray): I think if it need a redis lock for these 2 redis operation
        events_bin = await self._mem_db.lrange(event_queue_key, 0, -1)
        # Remove the got events.
        await self._mem_db.ltrim(event_queue_key, len(events_bin), -1)
        # Convert the events from binary to dictionary type.
        events = []
        for event_bin in events_bin:
            event_dict = jsonify(event_bin)
            event_dict['timestamp'] = int(event_dict['timestamp'])
            events.append(event_dict)
        return events

