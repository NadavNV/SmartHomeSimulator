import re
import logging
from typing import override
import random
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE, GENERAL_PARAMETERS
from device_types import DeviceType

DEFAULT_DIMMABLE = False
DEFAULT_BRIGHTNESS = 80
MIN_BRIGHTNESS = 0
MAX_BRIGHTNESS = 100
DEFAULT_DYNAMIC_COLOR = False
DEFAULT_COLOR = "#FFFFFF"
COLOR_REGEX = '^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$'

PARAMETERS: list[str] = [
    "brightness",
    "color",
    "is_dimmable",
    "dynamic_color",
]


class Light(Device):
    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "off",
            is_dimmable: bool = DEFAULT_DIMMABLE,
            brightness: int = DEFAULT_BRIGHTNESS,
            dynamic_color: bool = DEFAULT_DYNAMIC_COLOR,
            color: str = DEFAULT_COLOR,
    ):
        super().__init__(
            device_id=device_id,
            device_type=DeviceType.LIGHT,
            room=room,
            name=name,
            mqtt_client=mqtt_client,
            status=status,
            logger=logger,
        )
        self._is_dimmable = is_dimmable
        if MIN_BRIGHTNESS <= brightness <= MAX_BRIGHTNESS:
            self._brightness = brightness
        else:
            raise ValueError(f"Brightness must be between {MIN_BRIGHTNESS} and {MAX_BRIGHTNESS}")
        self._dynamic_color = dynamic_color
        if bool(re.match(COLOR_REGEX, color)):
            self._color = color
        else:
            raise ValueError(f"Color must be a valid hex code, got {color} instead.")

    @property
    def is_dimmable(self) -> bool:
        return self._is_dimmable

    @is_dimmable.setter
    def is_dimmable(self, value: bool) -> None:
        self._is_dimmable = value

    @property
    def brightness(self) -> int:
        return self._brightness

    @brightness.setter
    def brightness(self, value: int) -> None:
        if MIN_BRIGHTNESS <= value <= MAX_BRIGHTNESS:
            self._brightness = value
        else:
            raise ValueError(f"Brightness must be between {MIN_BRIGHTNESS} and {MAX_BRIGHTNESS}")

    @property
    def dynamic_color(self) -> bool:
        return self._dynamic_color

    @dynamic_color.setter
    def dynamic_color(self, value: bool) -> None:
        self._dynamic_color = value

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, value: str) -> None:
        if bool(re.match(COLOR_REGEX, value)):
            self._color = value
        else:
            raise ValueError(f"Color must be a valid hex code, got {value} instead.")

    @override
    def tick(self) -> None:
        """
        Actions to perform on every iteration of the main loop.
        - Randomly apply change
        - Publish changes to MQTT
        """
        action_parameters = {}
        update_parameters = {}
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            elements = ['status']
            if self.is_dimmable:
                elements.append('brightness')
            if self.dynamic_color:
                elements.append('color')
            element_to_change = random.choice(elements)
            match element_to_change:
                case 'status':
                    update_parameters['status'] = self.status = 'on' if self.status == 'off' else 'off'
                case 'brightness':
                    next_brightness = self.brightness
                    while next_brightness == self.brightness:
                        next_brightness = random.randint(MIN_BRIGHTNESS, MAX_BRIGHTNESS)
                    action_parameters['brightness'] = self.brightness = next_brightness
                case 'color':
                    next_color = int('0x' + self.color[1:], 16)
                    while next_color == int('0x' + self.color[1:], 16):
                        next_color = random.randrange(0, 2 ** 24)
                    action_parameters['color'] = self.color = "#" + hex(next_color)[2:]
                case _:
                    print(f"Unknown element {element_to_change}")
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
                        case "brightness":
                            self.brightness = value
                        case "color":
                            self.color = value
                        case "is_dimmable":
                            self.is_dimmable = value
                        case "dynamic_color":
                            self.color = value
                    self._logger.info(f"Setting parameter '{key}' to value '{value}'")
                except ValueError:
                    self._logger.exception(f"Incorrect value {value} for parameter {key}")
            else:
                raise ValueError(f"Incorrect parameter {key} for device type {self.type.value}")
