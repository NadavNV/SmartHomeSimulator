from typing import override
import random
import logging
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE, GENERAL_PARAMETERS
from device_types import DeviceType

DEFAULT_POSITION = 100
MIN_POSITION = 0
MAX_POSITION = 100
POSITION_RATE = 1


class Curtain(Device):
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
        Actions to perform on every iteration of the main loop.
        - Adjust position
        - Randomly apply status change
        - Publish changes to MQTT
        """
        action_parameters = {}
        update_parameters = {}
        # Adjust position
        if self.position > MIN_POSITION and self.status == "open":
            self.position -= POSITION_RATE
            action_parameters['position'] = self.position
        if self.position < MAX_POSITION and self.status == "closed":
            self.position += POSITION_RATE
            action_parameters['position'] = self.position
        # Randomly lock or unlock
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            update_parameters['status'] = self.status = "closed" if self.status == "open" else "open"
        self.publish_mqtt(action_parameters, update_parameters)

    @override
    def update(self, new_values: dict) -> None:
        for key, value in new_values.items():
            if key in GENERAL_PARAMETERS:
                try:
                    match key:
                        case "room":
                            self.room = value
                        case "name":
                            self.name = value
                        case "status":
                            self.status = value
                    self._logger.info(f"Setting parameter '{key}' to value '{value}'")
                except ValueError:
                    self._logger.exception(f"Incorrect value {value} for parameter {key}")
            else:
                raise ValueError(f"Incorrect parameter {key} for device type {self.type.value}")
