import json
import logging
import typing

import requests
from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver
import pyhap.const

from ._registry import register
from ..websocket import WebSocket


logger = logging.getLogger(__name__)


@register(type_="relay", icon="light")
class VelbusRelayLightBulb(Accessory):
    category = pyhap.const.CATEGORY_LIGHTBULB

    def __init__(
            self,
            driver: AccessoryDriver,
            websocket: WebSocket,
            display_name: str,
            velbus_base_url: str,
            velbus_module_address: typing.List[int],
    ):
        aid = 0
        for a in velbus_module_address:
            aid = aid * 256 + a

        super().__init__(
            driver=driver,
            display_name=display_name,
            aid=aid,
        )

        self.velbus_base_url = velbus_base_url
        self.websocket = websocket

        if len(velbus_module_address) != 2:
            raise ValueError(f"Expected 2 address components for Relay, got {len(velbus_module_address)}")
        self.velbus_module_address = velbus_module_address[0]
        self.velbus_module_channel = velbus_module_address[1]

        self.websocket.add_event_handler(
            path=[f"{self.velbus_module_address:02x}", f"{self.velbus_module_channel}"],
            cb=self.notify,
        )

        self.set_info_service(
            manufacturer="Velbus",
            model="relay",
            serial_number=f"0x{self.velbus_module_address:02x}-{self.velbus_module_channel}"
        )

        # IIDs are assigned in the order the services & characteristics are added.
        # Be careful when changing this!
        serv_light = self.add_preload_service('Lightbulb')
        self.char_on = serv_light.configure_char(
            'On',  # The "On"-characteristic is required for a Lightbulb
            setter_callback=self.set_bulb,
            getter_callback=self.get_bulb,
        )

    def set_bulb(self, value: int) -> None:
        """
        Request from a HomeKit Controller (e.g. iPhone) to change the bulb status
        :param value: desired state: 0, 1
        """
        value = False if value == 0 else True
        url = f"{self.velbus_base_url}/module/{self.velbus_module_address:02x}/{self.velbus_module_channel}/relay"
        data = json.dumps(value)
        logger.info(f"HTTP POST {url} data: {data!r}")
        resp = requests.put(url, data=data)
        if resp.status_code != 200:
            raise RuntimeError(f"Error updating Velbus state: {resp.reason}")

    def get_bulb(self) -> int:
        """
        Request from a HomeKit Controller (e.g. iPhone) for the current state of the bulb
        :return:
        """
        url = f"{self.velbus_base_url}/module/{self.velbus_module_address:02x}/{self.velbus_module_channel}/relay"
        logger.info(f"HTTP GET {url}")
        resp = requests.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"Error updating Velbus state for : {resp.reason}")

        return 1 if json.loads(resp.content) else 0

    def notify(self, state_dict: dict):
        logger.info(f"Websocket Rx: {self.velbus_module_address}/{self.velbus_module_channel}: {state_dict!r}")
        new_state = state_dict['relay']
        new_state = 1 if new_state else 0
        # Push new state to Controllers
        self.char_on.set_value(new_state)
