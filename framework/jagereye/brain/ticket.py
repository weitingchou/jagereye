import aioredis
from jagereye.brain.utils import jsonify, jsondumps


MEMDB_HOST = 'redis://localhost:6379'


async def create_ticket(loop):
    ticket = Ticket(loop)
    await ticket._setup()
    return ticket

def gen_key(id):
    return 'ticket:{}'.format(id)

class Ticket():
    def __init__(self, loop):
        self._loop = loop
        self._memdb = None

    async def _setup(self):
        self._memdb = await aioredis.create_redis(MEMDB_HOST, loop=self._loop)

    async def get(self, id):
        """Get ticket by ID.

        Args:
            id: ticket ID

        Returns:
            a dict object of ticket content
        """
        key = gen_key(id)
        return jsonify(await self._memdb.get(key))

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
        return await self._memdb.execute('setnx', key, jsondumps(context))

    async def delete(self, id):
        """Delete ticket.

        Args:
            id: ticket ID

        Returns:
            the number of tickets that were removed
        """
        key = gen_key(id)
        return await self._memdb.execute('del', key)
