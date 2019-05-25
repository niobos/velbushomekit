import asyncio
import logging
import json
import traceback
import typing

import time

import jsonpatch
import websockets


logger = logging.getLogger()


class WebSocket:
    def __init__(
            self,
            websocket_url: str,
            loop: asyncio.AbstractEventLoop,
    ):
        self.websocket_url = websocket_url
        self.loop = loop
        self.loop.create_task(self.run())

        self.handlers = dict()

        self._websocket = None
        self._state = {}

    def add_event_handler(
            self,
            path: typing.Iterable[str],
            cb: typing.Callable[[dict], None],
    ) -> asyncio.Future:
        """
        Register a callback to be called when updates are received at or below the given path
        :param path: Path to monitor
        :param cb: callback to be called. It will be called with a single argument,
                   the new (sub)dict rooted at the requested path
        :return: Future that resolves when the module is actually added
        """
        # self.handlers is a hierarchical structure containing the callbacks
        # Callbacks are saved in the None-key of the dict at the level they
        # registered:
        # add_event_handler(["a", "b"], cb1)
        #  =>
        #     {"a": {"b": {None: [cb1]}}
        # add_event_handler(["a"], cb2)
        #  =>
        #     {"a": {None: [cb2], "b": {None: [cb1]}}
        p = self.handlers
        for component in path:
            p = p.setdefault(component, {})
        p.setdefault(None, []).append(cb)

        task = self.loop.create_task(self.register_module(path[0]))
        return task

    async def register_module(self, hex_address: str):
        if self._websocket is None:
            return
        await self._websocket.send(json.dumps(
            [{"op": "add", "path": f"/{hex_address}", "value": True}]
        ))

    async def run(self) -> None:
        while True:
            try:
                async with websockets.connect(uri=self.websocket_url) as websocket:
                    logger.info("Websocket connected")
                    self._websocket = websocket
                    for hex_address in self.handlers.keys():
                        await self.register_module(hex_address)

                    async for message in self._websocket:
                        try:
                            message = json.loads(message)
                            for operation in message:
                                self.loop.create_task(self.dispatch(operation))
                                # fire and forget
                        except json.JSONDecodeError:
                            logger.error("Expected JSON message, but decode failed")
                        except TypeError:
                            logger.error("Expected a list of operations, but couldn't iterate")

            except Exception as e:
                self._websocket = None
                logger.error(f"WebSocket failed with exception: {e}")
                logger.error(traceback.format_exc())
                time.sleep(2)

    async def dispatch(self, operation: dict) -> None:
        jsonpatch.apply_patch(self._state, [operation], in_place=True)

        change_path = operation['path'].split('/')
        change_path.pop(0)  # strip leading empty element

        def notify_recursive(handlers: dict, change_path: typing.List[str], state: typing.Optional[dict]):
            for cb in handlers.get(None, []):
                cb(state)
            for key in handlers.keys():
                if key is None:
                    continue
                if len(change_path) and key != change_path[0]:
                    # Change is not in this key
                    continue

                state_under_key = state.get(key, None) if state is not None else None
                notify_recursive(handlers[key], change_path[1:], state_under_key)

        notify_recursive(self.handlers, change_path, self._state)
