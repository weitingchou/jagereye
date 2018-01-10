import aioredis
import json
import os, datetime

from jsonschema import Draft4Validator as Validator
from jagereye.brain.utils import jsonify
from jagereye.util import logging
from jagereye.util import static_util

# create event schema validator
with open(static_util.get_path('event.json'), 'r') as f:
    validator = Validator(json.loads(f.read()))


class EventAgent(object):
    def __init__(self, typename, mem_db, db):
        self._typename = typename
        self._mem_db = mem_db
        self._db = db

    def save_in_db(self, events, analyzer_id):
        """Save events into presistent db

        Args:
            events:(list of dict): the list of event
            analyzer_id:(string): the analyzer ID of the events

        Raises:
            TODO(Ray)
        """
        # validate
        valid_events = []
        for event in events:
            event['analyzer_id'] = analyzer_id
            if not validator.is_valid(event):
                logging.error('Fail validation for event {}'.format(event))
            else:
                event['date'] = datetime.datetime.fromtimestamp(event['timestamp'])
                valid_events.append(event)
        if valid_events:
            # TODO(Ray): error handler and logging if insert failed
            self._db.insert_many(valid_events)

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
            event_dict['timestamp'] = float(event_dict['timestamp'])
            events.append(event_dict)
        return events

