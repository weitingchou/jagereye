import aioredis
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
            a dict object of ticket content
        """
        key = gen_key(id)
        result = await self._mem_db.get(key)
        if result:
            return jsonify(result)
        else:
            return

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
