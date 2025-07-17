import config.env  # noqa: F401  # load_dotenv side effect
import json
import logging
import os
from datetime import time
from services.mqtt import get_mqtt, publish_mqtt
from device_types import DeviceType
from devices.light import Light
from devices.curtain import Curtain
from devices.door_lock import DoorLock
from devices.water_heater import WaterHeater
from devices.air_conditioner import AirConditioner, Mode, FanSpeed, Swing
from validation.validators import validate_device_data
from typing import Any, Mapping

CHANCE_TO_CHANGE: float = 0.01
GENERAL_PARAMETERS: set[str] = set(json.loads(os.getenv("DEVICE_PARAMETERS", '["room","name","status","parameters"]')))

logger = logging.getLogger("simulator.device")


# TODO: docstrings
def create_device(device_data: dict) -> None:
    success, reasons = validate_device_data(device_data, new_device=True)
    if not success:
        raise ValueError(f"{reasons}")
    if device_data["id"] in devices:
        raise ValueError(f"ID {device_data["id"]} already exists")
    kwargs = {
        'device_id': device_data['id'],
        'room': device_data['room'],
        'name': device_data['name'],
        'mqtt_client': get_mqtt(),
    }
    parameters = device_data.get("parameters", {})
    if 'status' in device_data:
        kwargs['status'] = device_data['status']
    kwargs.update(parameters)
    match device_data['type']:
        case DeviceType.WATER_HEATER:
            if 'scheduled_on' in kwargs:
                kwargs['scheduled_on'] = time.fromisoformat(
                    WaterHeater.fix_time_string(kwargs['scheduled_on'])
                )
            if 'scheduled_off' in kwargs:
                kwargs['scheduled_off'] = time.fromisoformat(
                    WaterHeater.fix_time_string(kwargs['scheduled_off'])
                )
            new_device = WaterHeater(**kwargs)
        case DeviceType.CURTAIN:
            new_device = Curtain(**kwargs)
        case DeviceType.DOOR_LOCK:
            new_device = DoorLock(**kwargs)
        case DeviceType.LIGHT:
            new_device = Light(**kwargs)
        case DeviceType.AIR_CONDITIONER:
            if 'mode' in kwargs:
                kwargs['mode'] = Mode(kwargs['mode'])
            if 'fan_speed' in kwargs:
                kwargs['fan_speed'] = FanSpeed(kwargs['fan_speed'])
            if 'swing' in kwargs:
                kwargs['swing'] = Swing(kwargs['swing'])
            new_device = AirConditioner(**kwargs)
        case _:
            raise ValueError(f"Unknown device type {device_data['type']}")
    if new_device is not None:
        devices[new_device.id] = new_device
        logger.info("Device added successfully")
        return
    else:
        logger.error(f"Failed to create device {device_data['id']}")
        return


class Device:

    def __init__(
            self,
            device_id: str,
            device_type: DeviceType,
            room: str,
            name: str,
            status: str,
    ):
        self._id: str = device_id
        self._type: DeviceType = device_type
        self._room: str = room
        self._name: str = name
        match self.type:
            case DeviceType.DOOR_LOCK:
                if status not in ['unlocked', 'locked']:
                    raise ValueError(f"Status of {self.type.value} must be either 'unlocked' or 'locked'")
            case DeviceType.CURTAIN:
                if status not in ['open', 'closed']:
                    raise ValueError(f"Status of {self.type.value} must be either 'open' or 'closed'")
            case _:
                if status not in ['on', 'off']:
                    raise ValueError(f"Status of {self.type.value} must be either 'on' or 'off'")
        self._status: str = status
        self._logger = logging.getLogger(f"smart-home.devices.{self.id}")

    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> DeviceType:
        return self._type

    @property
    def room(self) -> str:
        return self._room

    @room.setter
    def room(self, value: str) -> None:
        self._room = value

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        match self.type:
            case DeviceType.DOOR_LOCK:
                if value not in ['unlocked', 'locked']:
                    raise ValueError(f"Status of {self.type.value} must be either 'unlocked' or 'locked'")
            case DeviceType.CURTAIN:
                if value not in ['open', 'closed']:
                    raise ValueError(f"Status of {self.type.value} must be either 'open' or 'closed'")
            case _:
                if value not in ['on', 'off']:
                    raise ValueError(f"Status of {self.type.value} must be either 'on' or 'off'")
        self._status = value

    def tick(self) -> None:
        """
        Actions to perform on every iteration of the main loop. raises NotImplementedError()
        """
        raise NotImplementedError()

    def publish_mqtt(self, update: Mapping[str, Any]) -> None:
        publish_mqtt(self.id, update)

    def update(self, new_values: Mapping[str, Any]) -> None:
        for key, value in new_values.items():
            self._logger.info(f"Setting parameter '{key}' to value '{value}'")
            match key:
                case "room":
                    self.room = value
                case "name":
                    self.name = value
                case "status":
                    self.status = value
                case "parameters":
                    self.update_parameters(value)

    def update_parameters(self, new_values: Mapping[str, Any]):
        raise NotImplementedError()

    @staticmethod
    def str_to_bool(string: str) -> bool:
        """
        Converts strings such as "false" or "True" to their equivalent boolean value.

        :param str string: The string to convert
        :return: The boolean value
        :rtype: bool
        """
        return str(string).lower() == "true"


devices: dict[str, Device] = {}
