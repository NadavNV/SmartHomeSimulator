import config.env  # noqa: F401  # load_dotenv side effect
import re
import os
import json
import logging
from typing import Any, Mapping, override
import random
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE
from device_types import DeviceType


# Minimum brightness for dimmable light
MIN_BRIGHTNESS: int = int(os.getenv('VITE_MIN_BRIGHTNESS', 0))
# Maximum brightness for dimmable light
MAX_BRIGHTNESS: int = int(os.getenv("VITE_MAX_BRIGHTNESS", 100))
DEFAULT_DIMMABLE: bool = Device.str_to_bool(os.getenv("VITE_DEFAULT_DIMMABLE", "false"))
DEFAULT_BRIGHTNESS: int = int(os.getenv("VITE_DEFAULT_BRIGHTNESS", 80))
DEFAULT_DYNAMIC_COLOR: bool = Device.str_to_bool(os.getenv("VITE_DEFAULT_DYNAMIC_COLOR", "false"))
DEFAULT_COLOR: str = os.getenv("VITE_DEFAULT_LIGHT_COLOR", "#FFFFFF")
COLOR_REGEX: str = os.getenv("VITE_COLOR_REGEX", '^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$')

PARAMETERS: set[str] = set(json.loads(os.getenv("LIGHT_PARAMETERS", '["brightness","color","is_dimmable",'
                                                                    '"dynamic_color"]')))


class Light(Device):
    """
    Represents a smart light device with optional dimming and color-changing capabilities.

    Inherits from the base ``Device`` class and adds functionality specific to smart lights,
    such as brightness adjustment and color control.

    :param device_id: Unique identifier for the device.
    :type device_id: str
    :param room: Room where the device is located.
    :type room: str
    :param name: Human-readable name of the device.
    :type name: str
    :param mqtt_client: MQTT client instance for communication.
    :type mqtt_client: paho.mqtt.client.Client
    :param logger: Logger instance for logging device activity.
    :type logger: logging.Logger
    :param status: Initial status of the light (default is "off").
    :type status: str
    :param is_dimmable: Whether the light supports dimming.
    :type is_dimmable: bool
    :param brightness: Initial brightness level (must be within allowed range).
    :type brightness: int
    :param dynamic_color: Whether the light supports dynamic color changes.
    :type dynamic_color: bool
    :param color: Initial color of the light in hex format (e.g., "#FFFFFF").
    :type color: str

    :raises ValueError: If brightness is out of range or color is not a valid hex code.
    """
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
        """
        Indicates whether the light supports dimming.

        :return: True if the light is dimmable, False otherwise.
        :rtype: bool
        """
        return self._is_dimmable

    @property
    def brightness(self) -> int:
        """
        Gets or sets the brightness level of the light.

        :return: Current brightness value.
        :rtype: int

        :raises ValueError: If brightness is out of valid range.
        """
        return self._brightness

    @brightness.setter
    def brightness(self, value: int) -> None:
        if MIN_BRIGHTNESS <= value <= MAX_BRIGHTNESS:
            self._brightness = value
        else:
            raise ValueError(f"Brightness must be between {MIN_BRIGHTNESS} and {MAX_BRIGHTNESS}")

    @property
    def dynamic_color(self) -> bool:
        """
        Indicates whether the light supports dynamic color changes.

        :return: True if the light supports dynamic color, False otherwise.
        :rtype: bool
        """
        return self._dynamic_color

    @property
    def color(self) -> str:
        """
        Gets or sets the current color of the light.

        :return: Hex color string (e.g., "#FFFFFF").
        :rtype: str

        :raises ValueError: If the color is not a valid hex code.
        """
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
        Periodically called method to simulate state changes in the light.

        With a fixed probability, randomly changes one of the following attributes:
        - ``status`` (on/off)
        - ``brightness`` (if dimmable)
        - ``color`` (if dynamic color enabled)

        Changes are published to the MQTT broker.
        """
        update = {}
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
                    update['status'] = self.status = 'on' if self.status == 'off' else 'off'
                case 'brightness':
                    next_brightness = self.brightness
                    while next_brightness == self.brightness:
                        next_brightness = random.randint(MIN_BRIGHTNESS, MAX_BRIGHTNESS)
                    update.setdefault('parameters', {})['brightness'] = self.brightness = next_brightness
                case 'color':
                    next_color = int('0x' + self.color[1:], 16)
                    while next_color == int('0x' + self.color[1:], 16):
                        next_color = random.randrange(0, 2 ** 24)
                    update.setdefault('parameters', {})['color'] = self.color = "#" + hex(next_color)[2:].zfill(6)
                case _:
                    print(f"Unknown element {element_to_change}")
        self.publish_mqtt(update)

    @override
    def update_parameters(self, new_values: Mapping[str, Any]) -> None:
        """
        Updates one or more parameters of the light from an external source.

        Valid keys in ``new_values`` include:
        - ``brightness``
        - ``color``

        :param new_values: Dictionary mapping parameter names to new values.
        :type new_values: Mapping[str, Any]
        """
        for key, value in new_values.items():
            self._logger.info(f"Setting parameter '{key}' to value '{value}'")
            match key:
                case "brightness":
                    self.brightness = value
                case "color":
                    self.color = value
