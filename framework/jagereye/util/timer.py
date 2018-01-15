import asyncio
class Timer:
    def __init__(self, timeout, callback, *kwargs):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job(*kwargs))
    async def _job(self, *kwargs):
        await asyncio.sleep(self._timeout)
        await self._callback(*kwargs)
        self._task = asyncio.ensure_future(self._job(*kwargs))
    def cancel(self):
        self._task.cancel()
