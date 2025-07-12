import random
import logging
from datetime import datetime, time, timedelta
from typing import override

import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE, GENERAL_PARAMETERS
from device_types import DeviceType

# Celsius
MIN_TEMPERATURE = 49
MAX_TEMPERATURE = 60
ROOM_TEMPERATURE = 23
HEATING_RATE = 1

DEFAULT_SCHEDULED_ON = time.fromisoformat("06:30")
DEFAULT_SCHEDULED_OFF = time.fromisoformat("08:00")

PARAMETERS: list[str] = [
    "target_temperature",
    "timer_enabled",
    "scheduled_on",
    "scheduled_off",
]


class WaterHeater(Device):
    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "off",
            temperature: int = ROOM_TEMPERATURE,
            target_temperature: int = MIN_TEMPERATURE,
            is_heating: bool = False,
            timer_enabled: bool = False,
            scheduled_on: time = DEFAULT_SCHEDULED_ON,
            scheduled_off: time = DEFAULT_SCHEDULED_OFF,
    ):
        super().__init__(
            device_id=device_id,
            device_type=DeviceType.WATER_HEATER,
            room=room,
            name=name,
            mqtt_client=mqtt_client,
            status=status,
            logger=logger,
        )
        self._temperature: int = temperature
        if MIN_TEMPERATURE <= target_temperature <= MAX_TEMPERATURE:
            self._target_temperature = target_temperature
        else:
            raise ValueError(f"Temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}")
        self._is_heating: bool = is_heating
        self._timer_enabled: bool = timer_enabled
        self._scheduled_on: time = scheduled_on
        self._scheduled_off: time = scheduled_off

    @staticmethod
    def fix_time_string(string: str) -> str:
        if ":" not in string:
            raise ValueError(f"Invalid time string: {string}")
        hours, minutes = string.split(":")
        hours = hours.zfill(2)
        minutes = minutes.zfill(2)
        return f"{hours}:{minutes}"

    @property
    def temperature(self) -> int:
        return self._temperature

    @property
    def target_temperature(self) -> int:
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, value: int) -> None:
        if MIN_TEMPERATURE <= value <= MAX_TEMPERATURE:
            self._target_temperature = value
        else:
            raise ValueError(f"Temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}")

    @property
    def is_heating(self) -> bool:
        return self._is_heating

    @property
    def timer_enabled(self) -> bool:
        return self._timer_enabled

    @timer_enabled.setter
    def timer_enabled(self, value: bool) -> None:
        self._timer_enabled = value

    @property
    def scheduled_on(self) -> time:
        return self._scheduled_on

    @scheduled_on.setter
    def scheduled_on(self, value: time) -> None:
        self._scheduled_on = value

    @property
    def scheduled_off(self) -> time:
        return self._scheduled_off

    @scheduled_off.setter
    def scheduled_off(self, value: time) -> None:
        self._scheduled_off = value

    @override
    def tick(self) -> None:
        """
        Actions to perform on every iteration of the main loop.
        - Adjust temperature based on _is_heating
        - Adjust status based on timer
        - Adjust _is_heating based on status and target temperature
        - Randomly apply change
        - Publish changes to MQTT
        """
        action_parameters = {}
        update_parameters = {}
        # Adjusting temperature
        if self.is_heating:
            self._temperature += HEATING_RATE
            action_parameters['temperature'] = self.temperature
        elif self._temperature > ROOM_TEMPERATURE:
            self._temperature -= HEATING_RATE
            action_parameters['temperature'] = self.temperature
        # Adjusting status
        if self.timer_enabled:
            delta = timedelta(seconds=5)
            now = datetime.now()
            if (
                    self.status == "off" and
                    (now - delta <= datetime.combine(now.date(), self.scheduled_on) <= now + delta)
            ):
                update_parameters['status'] = self.status = "on"
            elif (
                    self.status == "on" and
                    (now - delta <= datetime.combine(now.date(), self.scheduled_off) <= now + delta)
            ):
                update_parameters['status'] = self.status = "off"
        # Adjusting is_heating
        if self.is_heating:
            self._logger.info("Is heating")
            if self.temperature >= self.target_temperature or self.status == "off":
                action_parameters["is_heating"] = self._is_heating = False
        elif self.status == "on" and self.temperature < self.target_temperature:
            action_parameters["is_heating"] = self._is_heating = True
        # Random change
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            element_to_change = random.choice(
                ['status', 'target_temperature', 'timer_enabled', 'scheduled_on', 'scheduled_off']
            )
            match element_to_change:
                case 'status':
                    update_parameters['status'] = self.status = 'on' if self.status == 'off' else 'off'
                case 'target_temperature':
                    next_temperature = self.target_temperature
                    while next_temperature == self.target_temperature:
                        next_temperature = random.randint(MIN_TEMPERATURE, MAX_TEMPERATURE)
                    action_parameters['target_temperature'] = self.target_temperature = next_temperature
                case 'timer_enabled':
                    action_parameters['timer_enabled'] = self.timer_enabled = not self.timer_enabled
                case 'scheduled_on':
                    next_time = self.scheduled_on
                    while next_time == self.scheduled_on:
                        next_time = time(
                            hour=random.randint(0, 23),
                            minute=random.randint(0, 59),
                        )
                    self.scheduled_on = next_time
                    action_parameters['scheduled_on'] = self.fix_time_string(
                        str(self.scheduled_on.hour).zfill(2) + ':' + str(self.scheduled_on.minute).zfill(2))
                case 'scheduled_off':
                    next_time = self.scheduled_off
                    while next_time == self.scheduled_off:
                        next_time = time(
                            hour=random.randint(0, 23),
                            minute=random.randint(0, 59),
                        )
                    self.scheduled_off = next_time
                    action_parameters['scheduled_off'] = self.fix_time_string(
                        str(self.scheduled_off.hour).zfill(2) + ':' + str(self.scheduled_off.minute).zfill(2))
                case _:
                    print(f"Unknown element {element_to_change}")
        # Publish changes
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
                        case "target_temperature":
                            self.target_temperature = value
                        case "timer_enabled":
                            self.timer_enabled = value
                        case "scheduled_on":
                            self.scheduled_on = time.fromisoformat(self.fix_time_string(value))
                        case "scheduled_off":
                            self.scheduled_off = time.fromisoformat(self.fix_time_string(value))
                    self._logger.info(f"Setting parameter '{key}' to value '{value}'")
                except ValueError:
                    self._logger.exception(f"Incorrect value {value} for parameter {key}")
            else:
                raise ValueError(f"Incorrect parameter {key} for device type {self.type.value}")
