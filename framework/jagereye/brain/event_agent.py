import aioredis
import json
import os

from jsonschema import Draft4Validator as Validator
from jagereye.brain.utils import jsonify

# create a schema validator with a json file
cuurent_path = os.path.dirname(__file__)
schema_path = os.path.join(cuurent_path, 'schema/event.json')
schema = json.load(open(schema_path))
validator = Validator(schema)

class EventAgent():
    def __init__(self, typename, mem_db, db):
        self._typename = typename
        self._mem_db = mem_db
        self._db = db

    def add_analyzer_field(self, events, analyzer_id):
        for event in events:
            event['analyzer_id'] = analyzer_id

    def store_in_db(self, events):
        # TODO(Ray): error handler and logging
        self._db[self._typename].insert_many(events)

    async def consume_from_worker(self, worker_id):
        """Get event array by worker ID.

        Args:
            worker_id: worker ID

        Returns:
            an array of event object
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
            events.append(jsonify(event_bin))
        return events

