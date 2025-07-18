import config.env  # noqa: F401  # load_dotenv side effect
from typing import Any, Mapping, override
import os
import json
import random

from devices.device import Device, CHANCE_TO_CHANGE
from devices.device_types import DeviceType

DEFAULT_LOCK_STATUS = os.getenv("VITE_DEFAULT_LOCK_STATUS", "unlocked")
DEFAULT_AUTO_LOCK: bool = Device.str_to_bool(os.getenv("VITE_DEFAULT_AUTO_LOCK_ENABLED", "False"))
DEFAULT_BATTERY: int = int(os.getenv("VITE_DEFAULT_BATTERY", 100))
MIN_BATTERY: int = int(os.getenv("MIN_BATTERY", 0))
MAX_BATTERY: int = int(os.getenv("MAX_BATTERY", 100))
BATTERY_DRAIN: int = 1

PARAMETERS: set[str] = set(json.loads(os.getenv("LOCK_PARAMETERS", '["auto_lock_enabled","battery_level"]')))


class DoorLock(Device):
    """
    Represents a smart door lock, with a possible auto-lock feature.

    :param device_id: Unique identifier for the device.
    :type device_id: str
    :param room: The room in which the device is located.
    :type room: str
    :param name: Display name for the device.
    :type name: str
    :param status: Current status ("unlocked" or "locked").
    :type status: str
    :param auto_lock_enabled: Whether the auto-lock feature is enabled initially.
    :type auto_lock_enabled: bool
    :param battery_level: Initial battery level percentage
    :type battery_level: int

    :raises ValueError: If battery level is outside allowed range.
    """

    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            status: str = DEFAULT_LOCK_STATUS,
            auto_lock_enabled: bool = DEFAULT_AUTO_LOCK,
            battery_level: int = DEFAULT_BATTERY,
    ):

        super().__init__(
            device_id=device_id,
            device_type=DeviceType.DOOR_LOCK,
            room=room,
            name=name,
            status=status,
        )
        self._auto_lock_enabled = auto_lock_enabled
        if MIN_BATTERY <= battery_level <= MAX_BATTERY:
            self._battery_level = battery_level
        else:
            raise ValueError(f"Battery level must be between {MIN_BATTERY} and {MAX_BATTERY}")

    @property
    def auto_lock_enabled(self) -> bool:
        """
        Get or set whether the auto-lock feature is currently enabled.

        :return: True if currently enabled, False otherwise
        :rtype: bool
        """
        return self._auto_lock_enabled

    @auto_lock_enabled.setter
    def auto_lock_enabled(self, value: bool) -> None:
        self._auto_lock_enabled = value

    @property
    def battery_level(self) -> int:
        """
        Get or set the current battery level.

        :return: Current battery level
        :rtype: int
        """
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
        update = {}
        # Drain battery
        if self.battery_level >= MIN_BATTERY:
            try:
                self.battery_level -= BATTERY_DRAIN
            except ValueError:
                self.battery_level = MAX_BATTERY
        update.setdefault('parameters', {})['battery_level'] = self.battery_level
        # Randomly lock or unlock
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            update['status'] = self.status = "locked" if self.status == "unlocked" else "unlocked"
        self.publish_mqtt(update)

    @override
    def update_parameters(self, new_values: Mapping[str, Any]) -> None:
        for key, value in new_values.items():
            self._logger.info(f"Setting parameter '{key}' to value '{value}'")
            match key:
                case "auto_lock_enabled":
                    self.auto_lock_enabled = value

    @override
    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["parameters"] = {
            "auto_lock_enabled": self.auto_lock_enabled,
            "battery_level": self.battery_level,
        }
        return result
