import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

CH_API_TO_BRAIN = "ch_api_brain"

async def run(loop):
    nc = NATS()

    await nc.connect(io_loop=loop)

    async def message_handler(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        print("Received a message on '{subject} {reply}': {data}".format(subject=subject, reply=reply, data=data))
    
    # Simple publisher and async subscriber via coroutine.
    #sid = yield from nc.subscribe(CHANNEL_NAME, cb=message_handler)

    request =   { 
            "action": "start",
            "name": "Tripwire",
            "params": {
                "bb": [],
                "triggers": ["person", "car"]
                }
            }

    await nc.request(CH_API_TO_BRAIN, str(request).encode(), cb=message_handler)
    await asyncio.sleep(5)
    await nc.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    loop.close()
