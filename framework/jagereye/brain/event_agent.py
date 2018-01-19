import aioredis
import json
import os, datetime

from pymongo.errors import OperationFailure as MongoOperationFailure

from jsonschema import Draft4Validator as Validator
from jagereye.brain.utils import jsonify
from jagereye.util import logging
from jagereye.util import static_util

# create event schema validator
with open(static_util.get_path('event.json'), 'r') as f:
    validator = Validator(json.loads(f.read()))

class EventAgent(object):
    def __init__(self, typename, mem_db, event_db, app_event_db):
        self._typename = typename
        self._mem_db = mem_db
        self._event_db = event_db
        self._app_event_db = app_event_db

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
        contents = []
        for event in events:
            contents.append(event['content'])
        # save all contents in self._app_event_db
        try:
            result  = self._app_event_db.insert_many(contents)
        except MongoOperationFailure as e:
            # TODO(Ray): error handler,
            # refered to https://stackoverflow.com/questions/35191042/get-inserted-ids-after-failed-insert-many
            # not yet test
            logging.error('{} error happened when save in db'.format(e))
            return False
        else:
            content_ids = result.inserted_ids
        for event,content_id in zip(events,content_ids):
            content_id = str(content_id)
            base_event = {
                    'analyzerId': analyzer_id,
                    'timestamp': event['timestamp'],
                    'type': event['type'],
                    'appName': event['app_name'],
                    'content': content_id
            }
            if not validator.is_valid(base_event):
                logging.error('Fail validation for event {}'.format(base_event))
            else:
                base_event['date'] = datetime.datetime.fromtimestamp(base_event['timestamp'])
                valid_events.append(base_event)
        if valid_events:
            # TODO(Ray): error handler and logging if insert failed
            result  = self._event_db.insert_many(valid_events)

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

