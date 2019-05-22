import json
import logging

import requests
from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver
import pyhap.const

from ._registry import register


logger = logging.getLogger(__name__)


@register(type_="relay", icon="light")
class VelbusRelayLightBulb(Accessory):
    category = pyhap.const.CATEGORY_LIGHTBULB

    def __init__(
            self,
            driver: AccessoryDriver,
            display_name: str,
            velbus_base_url: str,
            velbus_module_address: int,
            velbus_module_channel: int,
            aid=None,
    ):
        super().__init__(
            driver=driver,
            display_name=display_name,
            aid=aid,
        )

        self.velbus_base_url = velbus_base_url
        self.velbus_module_address = velbus_module_address
        self.velbus_module_channel = velbus_module_channel
        self.set_info_service(
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

    def notify(self, new_value):
        # Push new state to Controllers
        self.char_on.set_value(new_value)
