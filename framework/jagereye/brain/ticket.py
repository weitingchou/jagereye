import aioredis, time
from jagereye.brain.utils import jsonify, jsondumps

def gen_key(id):
    return 'ticket:{}'.format(id)

class TicketAgent():
    def __init__(self, mem_db):
        self._mem_db = mem_db

    async def get(self, id):
        """Get ticket by ID.

        Args:
            id: ticket ID

        Returns:
            dict: The ticket content if the ticket ID exists, None otherwise.
        """
        key = gen_key(id)
        result = await self._mem_db.get(key)
        if result:
            return jsonify(result)
        else:
            return None

    async def set(self, id, context):
        """Set ticket.

        Args:
            id: ticket ID

        Returns:
            1: ticket was set successfully
            0: ticket was not set because there existed a ticket with
               the same ID
        """
        key = gen_key(id)
        return await self._mem_db.execute('setnx', key, jsondumps(context))

    async def delete(self, id):
        """Delete ticket.

        Args:
            id: ticket ID

        Returns:
            the number of tickets that were removed
        """
        key = gen_key(id)
        return await self._mem_db.execute('del', key)

    async def set_many(self, anal_ids, params, command):
        mset_cmd = []
        timestamp = time.time()
        for anal_id, pipelines in zip(anal_ids, params):
            context = {
                'msg': {
                    'command': command,
                    'timestamp': timestamp,
                    'params': params
                }
            }

            mset_cmd.append(gen_key(anal_id))
            mset_cmd.append(jsondumps(context))
        return await self._mem_db.mset(*mset_cmd)

    async def delete_many(self, anal_ids):
        del_cmd = []
        for anal_id in anal_ids:
            del_cmd.append(gen_key(anal_id))
        return await self._mem_db.delete(*del_cmd)
