import config.env  # noqa: F401  # load_dotenv side effect
import json
import logging
import os
from main import client_id
import paho.mqtt.client as paho
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from device_types import DeviceType
from typing import Any, Mapping

CHANCE_TO_CHANGE: float = 0.01
GENERAL_PARAMETERS: set[str] = set(json.loads(os.getenv("DEVICE_PARAMETERS", '["room","name","status","parameters"]')))


class Device:

    def __init__(
            self,
            device_id: str,
            device_type: DeviceType,
            room: str,
            name: str,
            status: str,
            mqtt_client: paho.Client,
            logger: logging.Logger,
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
        self._mqtt_client = mqtt_client
        self._logger = logger

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
        topic = f"nadavnv-smart-home/devices{self.id}"
        properties = Properties(PacketTypes.PUBLISH)
        properties.UserProperty = [("sender_id", client_id), ("sender_group", "simulator")]
        payload = json.dumps({
            "contents": update,
        })
        self._mqtt_client.publish(topic + "/action", payload.encode(), qos=2, properties=properties)

    def update(self, new_values: Mapping[str, Any]) -> None:
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
                        case "parameters":
                            self.update_parameters(value)
                    self._logger.info(f"Setting parameter '{key}' to value '{value}'")
                except ValueError:
                    self._logger.exception(f"Incorrect value {value} for parameter {key}")
            else:
                raise ValueError(f"Incorrect parameter {key}")

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
