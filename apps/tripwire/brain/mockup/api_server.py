import asyncio
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

CHANNEL_NAME = "ch_api_brain"

def run(loop):
    nc = NATS()

    yield from nc.connect(io_loop=loop)

    @asyncio.coroutine
    def message_handler(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        print("Received a message on '{subject} {reply}': {data}".format(subject=subject, reply=reply, data=data))
    
    # Simple publisher and async subscriber via coroutine.
    #sid = yield from nc.subscribe(CHANNEL_NAME, cb=message_handler)

    request =   { 
                    "api_id": 1, 
                    "brain_id": 1, 
                    "task":
                    {
                        "verb": "create",
                        "src": 
                        {
                            "rtsp": "rtsp://192.168.0.3"
                        }
                    }
                }

    yield from nc.publish(CHANNEL_NAME, str(request).encode())
    #yield from asyncio.sleep(5, loop=loop)


    yield from nc.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(loop))
    loop.close()
