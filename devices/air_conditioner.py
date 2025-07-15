import json

import config.env  # noqa: F401  # load_dotenv side effect
import logging
import os
from enum import auto, StrEnum
from typing import Any, Mapping, override
import random
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE
from device_types import DeviceType


class Mode(StrEnum):
    COOL = auto()
    HEAT = auto()
    FAN = auto()


class FanSpeed(StrEnum):
    OFF = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


class Swing(StrEnum):
    OFF = auto()
    ON = auto()
    AUTO = auto()


# Minimum temperature (Celsius) for air conditioner
MIN_AC_TEMP: int = int(os.getenv('VITE_MIN_AC_TEMP', 16))
# Maximum temperature (Celsius) for air conditioner
MAX_AC_TEMP: int = int(os.getenv('VITE_MAX_AC_TEMP', 30))

DEFAULT_AC_TEMPERATURE: int = int(os.getenv("VITE_DEFAULT_AC_TEMP", 24))
DEFAULT_MODE: Mode = Mode(value=os.getenv("VITE_DEFAULT_AC_MODE", "cool"))
DEFAULT_FAN: FanSpeed = FanSpeed(value=os.getenv("VITE_DEFAULT_AC_FAN", "low"))
DEFAULT_SWING: Swing = Swing(value=os.getenv("VITE_DEFAULT_AC_SWING", "off"))

PARAMETERS: set[str] = set(json.loads(os.getenv("AC_PARAMETERS", "[\"temperature\",\"mode\",\"fan_speed\",\"swing\"]")))


class AirConditioner(Device):
    """
    Represents a smart air conditioner device with adjustable parameters such as
    temperature, mode, fan speed, and swing.

    :param device_id: Unique identifier for the device.
    :type device_id: str
    :param room: The room in which the device is located.
    :type room: str
    :param name: Display name for the device.
    :type name: str
    :param mqtt_client: MQTT client instance for publishing/subscribing messages.
    :type mqtt_client: paho.Client
    :param logger: Logger instance for event logging.
    :type logger: logging.Logger
    :param status: Device power status, either "on" or "off".
    :type status: str
    :param temperature: Initial temperature setting in Celsius.
    :type temperature: int
    :param mode: Initial operation mode (cool, heat, fan).
    :type mode: Mode
    :param fan_speed: Initial fan speed setting.
    :type fan_speed: FanSpeed
    :param swing: Initial swing setting.
    :type swing: Swing

    :raises ValueError: If temperature is outside allowed range.
    """
    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "off",
            temperature: int = DEFAULT_AC_TEMPERATURE,
            mode: Mode = DEFAULT_MODE,
            fan_speed: FanSpeed = DEFAULT_FAN,
            swing: Swing = DEFAULT_SWING
    ):
        super().__init__(
            device_id=device_id,
            device_type=DeviceType.AIR_CONDITIONER,
            room=room,
            name=name,
            mqtt_client=mqtt_client,
            status=status,
            logger=logger,
        )
        if MIN_AC_TEMP <= temperature <= MAX_AC_TEMP:
            self._temperature: int = temperature
        else:
            raise ValueError(f"Temperature must be between {MIN_AC_TEMP} and {MAX_AC_TEMP}")
        self._mode: Mode = mode
        self._fan_speed: FanSpeed = fan_speed
        self._swing: Swing = swing

    @property
    def temperature(self) -> int:
        """
        Gets or sets the temperature.

        :return: Current temperature value.
        :rtype: int

        :raises ValueError: If temperature is out of valid range.
        """
        return self._temperature

    @temperature.setter
    def temperature(self, temperature) -> None:
        if MIN_AC_TEMP <= temperature <= MAX_AC_TEMP:
            self._temperature: int = temperature
        else:
            raise ValueError(f"Temperature must be between {MIN_AC_TEMP} and {MAX_AC_TEMP}")

    @property
    def mode(self) -> Mode:
        """
        Gets or sets the mode of the air conditioner.

        :return: Current mode.
        :rtype: Mode
        """
        return self._mode

    @mode.setter
    def mode(self, value: Mode) -> None:
        self._mode = value

    @property
    def fan_speed(self) -> FanSpeed:
        """
        Gets or sets the fan speed of the air conditioner.

        :return: Current fan speed.
        :rtype: FanSpeed
        """
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, value: FanSpeed) -> None:
        self._fan_speed = value

    @property
    def swing(self) -> Swing:
        """
        Gets or sets the swing mode of the air conditioner.

        :return: Current swing mode.
        :rtype: Swing
        """
        return self._swing

    @swing.setter
    def swing(self, value: Swing) -> None:
        self._swing = value

    @override
    def tick(self) -> None:
        """
        Called on each simulation tick:
        - Randomly changes one parameter (status, temperature, etc.)
        - Publishes updated state to MQTT.
        """
        update = {}
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            element_to_change = random.choice(['status', 'temperature', 'mode', 'fan_speed', 'swing'])
            match element_to_change:
                case 'status':
                    update['status'] = self.status = 'on' if self.status == 'off' else 'off'
                case 'temperature':
                    next_temperature = self.temperature
                    while next_temperature == self.temperature:
                        next_temperature = random.randint(MIN_AC_TEMP, MAX_AC_TEMP)
                    update.setdefault('parameters', {})['temperature'] = self.temperature = next_temperature
                case 'mode':
                    next_mode = self.mode
                    while next_mode == self.mode:
                        next_mode = random.choice(list(Mode))
                    update.setdefault('parameters', {})['mode'] = self.mode = next_mode
                case 'fan_speed':
                    next_speed = self.fan_speed
                    while next_speed == self.fan_speed:
                        next_speed = random.choice(list(FanSpeed))
                    update.setdefault('parameters', {})['fan_speed'] = self.fan_speed = next_speed
                case 'swing':
                    next_swing = self.swing
                    while next_swing == self.swing:
                        next_swing = random.choice(list(Swing))
                    update.setdefault('parameters', {})['swing'] = self.swing = next_swing
                case _:
                    print(f"Unknown element {element_to_change}")
        self.publish_mqtt(update)

    @override
    def update_parameters(self, new_values: Mapping[str, Any]) -> None:
        """
        Updates device parameters from a given dictionary.

        :param new_values: Dictionary containing parameter keys and values.
        :raises ValueError: If any key or value is invalid for this device.
        """
        for key, value in new_values.items():
            self._logger.info(f"Setting parameter '{key}' to value '{value}'")
            match key:
                case "temperature":
                    self.temperature = value
                case "mode":
                    self.mode = Mode(value=value)
                case "fan_speed":
                    self.fan_speed = FanSpeed(value=value)
                case "swing":
                    self.swing = Swing(value=value)
