import logging
from enum import auto, StrEnum
from typing import override
import random
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE, GENERAL_PARAMETERS
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


# Celsius
DEFAULT_TEMPERATURE = 24
MIN_TEMPERATURE = 16
MAX_TEMPERATURE = 30

DEFAULT_MODE = Mode.COOL
DEFAULT_FAN = FanSpeed.MEDIUM
DEFAULT_SWING = Swing.OFF

PARAMETERS: list[str] = [
    "temperature",
    "mode",
    "fan_speed",
    "swing"
]


class AirConditioner(Device):

    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "off",
            temperature: int = DEFAULT_TEMPERATURE,
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
        if MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE:
            self._temperature: int = temperature
        else:
            raise ValueError(f"Temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}")
        self._mode: Mode = mode
        self._fan_speed: FanSpeed = fan_speed
        self._swing: Swing = swing

    @property
    def temperature(self) -> int:
        return self._temperature

    @temperature.setter
    def temperature(self, temperature) -> None:
        if MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE:
            self._temperature: int = temperature
        else:
            raise ValueError(f"Temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}")

    @property
    def mode(self) -> Mode:
        return self._mode

    @mode.setter
    def mode(self, value: Mode) -> None:
        self._mode = value

    @property
    def fan_speed(self) -> FanSpeed:
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, value: FanSpeed) -> None:
        self._fan_speed = value

    @property
    def swing(self) -> Swing:
        return self._swing

    @swing.setter
    def swing(self, value: Swing) -> None:
        self._swing = value

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
            element_to_change = random.choice(['status', 'temperature', 'mode', 'fan_speed', 'swing'])
            match element_to_change:
                case 'status':
                    update_parameters['status'] = self.status = 'on' if self.status == 'off' else 'off'
                case 'temperature':
                    next_temperature = self.temperature
                    while next_temperature == self.temperature:
                        next_temperature = random.randint(MIN_TEMPERATURE, MAX_TEMPERATURE)
                    action_parameters['temperature'] = self.temperature = next_temperature
                case 'mode':
                    next_mode = self.mode
                    while next_mode == self.mode:
                        next_mode = random.choice(list(Mode))
                    action_parameters['mode'] = self.mode = next_mode
                case 'fan_speed':
                    next_speed = self.fan_speed
                    while next_speed == self.fan_speed:
                        next_speed = random.choice(list(FanSpeed))
                    action_parameters['fan_speed'] = self.fan_speed = next_speed
                case 'swing':
                    next_swing = self.swing
                    while next_swing == self.swing:
                        next_swing = random.choice(list(Swing))
                    action_parameters['swing'] = self.swing = next_swing
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
                        case "temperature":
                            self.temperature = value
                        case "mode":
                            self.mode = Mode(value=value)
                        case "fan_speed":
                            self.fan_speed = FanSpeed(value=value)
                        case "swing":
                            self.swing = Swing(value=value)
                    self._logger.info(f"Setting parameter '{key}' to value '{value}'")
                except ValueError:
                    self._logger.exception(f"Incorrect value {value} for parameter {key}")
            else:
                raise ValueError(f"Incorrect parameter {key} for device type {self.type.value}")
