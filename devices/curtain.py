import config.env  # noqa: F401  # load_dotenv side effect
from typing import Any, Mapping, override
import os
import random
import logging
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE
from device_types import DeviceType

DEFAULT_POSITION: int = int(os.getenv("VITE_DEFAULT_POSITION", 100))
MIN_POSITION: int = int(os.getenv("MIN_POSITION", 0))
MAX_POSITION: int = int(os.getenv("MAX_POSITION", 100))
POSITION_RATE: int = 1


class Curtain(Device):
    """
    Represents a smart curtain device with position control and open/closed state.

    :param device_id: Unique identifier for the curtain.
    :type device_id: str
    :param room: Room where the curtain is located.
    :type room: str
    :param name: Name of the curtain.
    :type name: str
    :param mqtt_client: MQTT client used for communication.
    :type mqtt_client: paho.Client
    :param logger: Logger for debugging and tracking state.
    :type logger: logging.Logger
    :param status: Current status ("open" or "closed").
    :type status: str
    :param position: Initial position of the curtain (0–100).
    :type position: int

    :raises ValueError: If initial position is out of allowed bounds.
    """
    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "off",
            position: int = DEFAULT_POSITION,
    ):
        super().__init__(
            device_id=device_id,
            device_type=DeviceType.CURTAIN,
            room=room,
            name=name,
            mqtt_client=mqtt_client,
            status=status,
            logger=logger,
        )
        if MIN_POSITION <= position <= MAX_POSITION:
            self._position = position
        else:
            raise ValueError(f"Position must be between {MIN_POSITION} and {MAX_POSITION}")

    @property
    def position(self) -> int:
        """
        Gets or sets the curtain's position.

        :return: Current position.
        :rtype: int

        :raises ValueError: If position is out of valid range.
        """
        return self._position

    @position.setter
    def position(self, value: int) -> None:
        if MIN_POSITION <= value <= MAX_POSITION:
            self._position = value
        else:
            raise ValueError(f"Position must be between {MIN_POSITION} and {MAX_POSITION}")

    @override
    def tick(self) -> None:
        """
        Called on each simulation tick:
        - Adjusts curtain position based on its open/closed status.
        - Randomly toggles curtain status.
        - Publishes updated state to MQTT.
        """
        update = {}
        # Adjust position
        if self.position > MIN_POSITION and self.status == "open":
            self.position -= POSITION_RATE
            update.setdefault('parameters', {})['position'] = self.position
        if self.position < MAX_POSITION and self.status == "closed":
            self.position += POSITION_RATE
            update.setdefault('parameters', {})['position'] = self.position
        # Randomly lock or unlock
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            update['status'] = self.status = "closed" if self.status == "open" else "open"
        self.publish_mqtt(update)

    @override
    def update_parameters(self, new_values: Mapping[str, Any]) -> None:
        """
        Placeholder for curtain parameter updates. Not implemented.
        """
        pass
