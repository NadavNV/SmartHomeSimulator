import json
import logging
from main import client_id
import paho.mqtt.client as paho
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from device_types import DeviceType

CHANCE_TO_CHANGE = 0.01
GENERAL_PARAMETERS: list[str] = [
    "room",
    "name",
    "status"
]


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
        Actions to perform on every iteration of the main loop
        """
        raise NotImplementedError()

    def publish_mqtt(self, action_parameters: dict, update_parameters) -> None:
        topic = f"project/home/{self.id}"
        properties = Properties(PacketTypes.PUBLISH)
        properties.UserProperty = [("sender_id", client_id)]
        if action_parameters:
            payload = json.dumps({
                "contents": action_parameters,
            })
            self._mqtt_client.publish(topic + "/action", payload.encode(), qos=2, properties=properties)
        if update_parameters:
            payload = json.dumps({
                "contents": update_parameters,
            })
            self._mqtt_client.publish(topic + "/update", payload.encode(), qos=2, properties=properties)

    def update(self, new_values: dict) -> None:
        raise NotImplementedError()
