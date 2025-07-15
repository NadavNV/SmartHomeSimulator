import config.env  # noqa: F401  # load_dotenv side effect
import os
import json
import random
import logging
from typing import Any, Mapping, override
from datetime import datetime, time, timedelta
import paho.mqtt.client as paho

from device import Device, CHANCE_TO_CHANGE
from device_types import DeviceType

# Minimum temperature (Celsius) for water heater
MIN_WATER_TEMP: int = int(os.getenv('VITE_MIN_WATER_TEMP', 49))
# Maximum temperature (Celsius) for water heater
MAX_WATER_TEMP: int = int(os.getenv('VITE_MAX_WATER_TEMP', 60))
ROOM_TEMPERATURE: int = 23
HEATING_RATE: int = 1

DEFAULT_SCHEDULED_ON: time = time.fromisoformat(os.getenv("VITE_DEFAULT_START_TIME", "06:30"))
DEFAULT_SCHEDULED_OFF: time = time.fromisoformat(os.getenv("VITE_DEFAULT_STOP_TIME", "08:00"))

PARAMETERS: set[str] = set(json.loads(os.getenv("WATER_HEATER_PARAMETERS", '["temperature","target_temperature",'
                                                                           '"is_heating","timer_enabled",'
                                                                           '"scheduled_on","scheduled_off"]')))


class WaterHeater(Device):
    """
    Represents a smart water heater device with temperature control and scheduling.

    :param device_id: Unique identifier for the heater.
    :type device_id: str
    :param room: Room where the heater is located.
    :type room: str
    :param name: Display name of the device.
    :type name: str
    :param mqtt_client: MQTT communication client.
    :type mqtt_client: paho.Client
    :param logger: Logger for status and errors.
    :type logger: logging.Logger
    :param status: Power status ("on" or "off").
    :type status: str
    :param temperature: Current water temperature.
    :type temperature: int
    :param target_temperature: Desired water temperature.
    :type target_temperature: int
    :param is_heating: Whether the heater is actively heating.
    :type is_heating: bool
    :param timer_enabled: Whether scheduled start/stop is active.
    :type timer_enabled: bool
    :param scheduled_on: Scheduled start time.
    :type scheduled_on: time
    :param scheduled_off: Scheduled stop time.
    :type scheduled_off: time

    :raises ValueError: If target_temperature is out of allowed range.
    """
    def __init__(
            self,
            device_id: str,
            room: str,
            name: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
            status: str = "off",
            temperature: int = ROOM_TEMPERATURE,
            target_temperature: int = MIN_WATER_TEMP,
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
        if MIN_WATER_TEMP <= target_temperature <= MAX_WATER_TEMP:
            self._target_temperature = target_temperature
        else:
            raise ValueError(f"Temperature must be between {MIN_WATER_TEMP} and {MAX_WATER_TEMP}")
        self._is_heating: bool = is_heating
        self._timer_enabled: bool = timer_enabled
        self._scheduled_on: time = scheduled_on
        self._scheduled_off: time = scheduled_off

    @staticmethod
    def fix_time_string(string: str) -> str:
        """
        Normalizes a time string to HH:MM or HH:MM:SS format.

        :param string: Raw time string.
        :return: Properly formatted time string.

        :raises ValueError: If input format is invalid.
        """
        if ":" not in string:
            raise ValueError(f"Invalid time string: {string}")
        string = string.split(":")
        if len(string) == 2:
            hours, minutes = string
            hours = hours.zfill(2)
            minutes = minutes.zfill(2)
            return f"{hours}:{minutes}"
        elif len(string) == 3:
            hours, minutes, seconds = string
            hours = hours.zfill(2)
            minutes = minutes.zfill(2)
            seconds = seconds.zfill(2)
            return f"{hours}:{minutes}:{seconds}"
        else:
            raise ValueError(f"Invalid time string: {string}")

    @property
    def temperature(self) -> int:
        """
        Returns current water temperature. Read only.

        :return: Current water temperature.
        :rtype: int
        """
        return self._temperature

    @property
    def target_temperature(self) -> int:
        """
        Gets and sets the desired temperature for the water heater.

        :return: Current desired temperature
        :rtype: int

        :raises ValueError: If target temperature is out of valid range
        """
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, value: int) -> None:
        if MIN_WATER_TEMP <= value <= MAX_WATER_TEMP:
            self._target_temperature = value
        else:
            raise ValueError(f"Temperature must be between {MIN_WATER_TEMP} and {MAX_WATER_TEMP}")

    @property
    def is_heating(self) -> bool:
        """
        Indicates whether the water is currently heating. Read only.

        :return: True if water is currently heating, False otherwise.
        :rtype: bool
        """
        return self._is_heating

    @property
    def timer_enabled(self) -> bool:
        """
        Get or set whether scheduled start/stop is active.

        :return: Whether scheduled start/stop is currently active
        :rtype bool
        """
        return self._timer_enabled

    @timer_enabled.setter
    def timer_enabled(self, value: bool) -> None:
        self._timer_enabled = value

    @property
    def scheduled_on(self) -> time:
        """
        Get or set the time to turn on heating, if timer is enabled.

        :return: Current scheduled start time.
        :rtype: time
        """
        return self._scheduled_on

    @scheduled_on.setter
    def scheduled_on(self, value: time) -> None:
        self._scheduled_on = value

    @property
    def scheduled_off(self) -> time:
        """
        Get or set the time to turn off heating, if timer is enabled.

        :return: Current scheduled stop time.
        :rtype: time
        """
        return self._scheduled_off

    @scheduled_off.setter
    def scheduled_off(self, value: time) -> None:
        self._scheduled_off = value

    @override
    def tick(self) -> None:
        """
        Called on each simulation tick:
        - Adjusts water temperature.
        - Enables/disables heating based on schedule and target.
        - Randomly updates parameters.
        - Publishes updated state to MQTT.
        """
        update = {}
        # Adjusting temperature
        if self.is_heating:
            self._temperature += HEATING_RATE
            update.setdefault('parameters', {})['temperature'] = self.temperature
        elif self._temperature > ROOM_TEMPERATURE:
            self._temperature -= HEATING_RATE
            update.setdefault('parameters', {})['temperature'] = self.temperature
        # Adjusting status
        if self.timer_enabled:
            delta = timedelta(seconds=5)
            now = datetime.now()
            if (
                    self.status == "off" and
                    (now - delta <= datetime.combine(now.date(), self.scheduled_on) <= now + delta)
            ):
                update['status'] = self.status = "on"
            elif (
                    self.status == "on" and
                    (now - delta <= datetime.combine(now.date(), self.scheduled_off) <= now + delta)
            ):
                update['status'] = self.status = "off"
        # Adjusting is_heating
        if self.is_heating:
            self._logger.info("Is heating")
            if self.temperature >= self.target_temperature or self.status == "off":
                update.setdefault('parameters', {})["is_heating"] = self._is_heating = False
        elif self.status == "on" and self.temperature < self.target_temperature:
            update.setdefault('parameters', {})["is_heating"] = self._is_heating = True
        # Random change
        random.seed()
        if random.random() < CHANCE_TO_CHANGE:
            element_to_change = random.choice(
                ['status', 'target_temperature', 'timer_enabled', 'scheduled_on', 'scheduled_off']
            )
            match element_to_change:
                case 'status':
                    update['status'] = self.status = 'on' if self.status == 'off' else 'off'
                case 'target_temperature':
                    next_temperature = self.target_temperature
                    while next_temperature == self.target_temperature:
                        next_temperature = random.randint(MIN_WATER_TEMP, MAX_WATER_TEMP)
                    update.setdefault('parameters', {})[
                        'target_temperature'] = self.target_temperature = next_temperature
                case 'timer_enabled':
                    update.setdefault('parameters', {})['timer_enabled'] = self.timer_enabled = not self.timer_enabled
                case 'scheduled_on':
                    next_time = self.scheduled_on
                    while next_time == self.scheduled_on:
                        next_time = time(
                            hour=random.randint(0, 23),
                            minute=random.randint(0, 59),
                        )
                    self.scheduled_on = next_time
                    update.setdefault('parameters', {})['scheduled_on'] = self.fix_time_string(
                        str(self.scheduled_on.hour).zfill(2) + ':' + str(self.scheduled_on.minute).zfill(2))
                case 'scheduled_off':
                    next_time = self.scheduled_off
                    while next_time == self.scheduled_off:
                        next_time = time(
                            hour=random.randint(0, 23),
                            minute=random.randint(0, 59),
                        )
                    self.scheduled_off = next_time
                    update.setdefault('parameters', {})['scheduled_off'] = self.fix_time_string(
                        str(self.scheduled_off.hour).zfill(2) + ':' + str(self.scheduled_off.minute).zfill(2))
                case _:
                    print(f"Unknown element {element_to_change}")
        # Publish changes
        self.publish_mqtt(update)

    @override
    def update_parameters(self, new_values: Mapping[str, Any]) -> None:
        """
        Updates the heater’s parameters based on a dictionary input.

        :param new_values: Mapping of parameter names to values.
        :type new_values: Mapping[str, Any]
        """
        for key, value in new_values.items():
            self._logger.info(f"Setting parameter '{key}' to value '{value}'")
            match key:
                case "target_temperature":
                    self.target_temperature = value
                case "timer_enabled":
                    self.timer_enabled = value
                case "scheduled_on":
                    self.scheduled_on = time.fromisoformat(self.fix_time_string(value))
                case "scheduled_off":
                    self.scheduled_off = time.fromisoformat(self.fix_time_string(value))
