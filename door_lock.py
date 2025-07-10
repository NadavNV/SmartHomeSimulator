from typing import override
import random
import logging
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE, GENERAL_PARAMETERS
from device_types import DeviceType

DEFAULT_AUTO_LOCK = False
DEFAULT_BATTERY = 100
MIN_BATTERY = 0
MAX_BATTERY = 100
BATTERY_DRAIN = 1

PARAMETERS: list[str] = [
    "auto_lock_enabled",
]


class DoorLock(Device):
    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "unlocked",
            auto_lock_enabled: bool = DEFAULT_AUTO_LOCK,
            battery_level: int = DEFAULT_BATTERY,
    ):
        super().__init__(
            device_id=device_id,
            device_type=DeviceType.DOOR_LOCK,
            room=room,
            name=name,
            mqtt_client=mqtt_client,
            status=status,
            logger=logger,
        )
        self._auto_lock_enabled = auto_lock_enabled
        if MIN_BATTERY <= battery_level <= MAX_BATTERY:
            self._battery_level = battery_level
        else:
            raise ValueError(f"Battery level must be between {MIN_BATTERY} and {MAX_BATTERY}")

    @property
    def auto_lock_enabled(self) -> bool:
        return self._auto_lock_enabled

    @auto_lock_enabled.setter
    def auto_lock_enabled(self, value: bool) -> None:
        self._auto_lock_enabled = value

    @property
    def battery_level(self) -> int:
        return self._battery_level

    @battery_level.setter
    def battery_level(self, value: int) -> None:
        if MIN_BATTERY <= value <= MAX_BATTERY:
            self._battery_level = value
        else:
            raise ValueError(f"Battery level must be between {MIN_BATTERY} and {MAX_BATTERY}")

    @override
    def tick(self) -> None:
        """
        Actions to perform on every iteration of the main loop.
        - Drain battery
        - Randomly apply status change
        - Publish changes to MQTT
        """
        action_parameters = {}
        update_parameters = {}
        # Drain battery
        if self.battery_level >= MIN_BATTERY:
            try:
                self.battery_level -= BATTERY_DRAIN
            except ValueError:
                self.battery_level = MAX_BATTERY
        action_parameters['battery_level'] = self.battery_level
        # Randomly lock or unlock
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            update_parameters['status'] = self.status = "locked" if self.status == "unlocked" else "unlocked"
        self.publish_mqtt(action_parameters, update_parameters)

    @override
    def update(self, new_values: dict) -> None:
        for key, value in new_values.items():
            if key in PARAMETERS + GENERAL_PARAMETERS:
                try:
                    match key:
                        case "room":
                            self.room = value
                        case "name":
                            self.name = value
                        case "status":
                            self.status = value
                        case "auto_lock_enabled":
                            self.auto_lock_enabled = value
                    self._logger.info(f"Setting parameter '{key}' to value '{value}'")
                except ValueError:
                    self._logger.exception(f"Incorrect value {value} for parameter {key}")
            else:
                raise ValueError(f"Incorrect parameter {key} for device type {self.type.value}")
