from config import env  # noqa: F401  # load_dotenv side effect
import os
import logging
from typing import Any, cast, Mapping
import paho.mqtt.client as paho
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
import json
from core.device_utils import create_device, devices
from validation.validators import validate_device_data


class MQTTNotInitializedError(Exception):
    """Raised when the MQTT client is accessed before initialization."""
    pass


# Setting up the MQTT client
BROKER_HOST = os.getenv("BROKER_HOST", "test.mosquitto.org")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "nadavnv-smart-home/devices")
CLIENT_ID = f"simulator-{os.getenv('HOSTNAME')}"

logger = logging.getLogger("simulator.mqtt")

mqtt_client: paho.Client | None = None
mqtt_connected = False


# TODO: docstrings
def on_connect(client, _userdata, _connect_flags, reason_code, _properties):
    global mqtt_connected
    logger.info(f'CONNACK received with code {reason_code}.')
    if reason_code == 0:
        with open("./status", "a") as file:
            file.write("ready\n")
            mqtt_connected = True
        logger.info("Connected successfully")
        client.subscribe(f"$share/simulator/{MQTT_TOPIC}/#")


def on_disconnect(_client, _userdata, _disconnect_flags, reason_code, _properties=None):
    global mqtt_connected
    if reason_code == 0:
        logger.warning(f"Disconnected from broker.")
    else:
        logger.warning(f"Disconnected from broker with reason: {reason_code}")
    mqtt_connected = False
    with open("./status", "w") as file:
        file.write("healthy\n")


def on_subscribe(
        _client: paho.Client,
        _userdata: Any,
        _mid: int,
        reason_code_list: list[paho.ReasonCodes],
        _properties: paho.Properties,
):
    for rc in reason_code_list:
        logger.info(f"Subscribed with reason code {rc}")


def on_message(
        _client: paho.Client,
        _userdata: Any,
        msg: paho.MQTTMessage,
):
    sender_id, sender_group = None, None
    props = msg.properties
    user_props = getattr(props, "UserProperty", None)
    if user_props is not None:
        sender_id = dict(user_props).get("sender_id")
        sender_group = dict(user_props).get("sender_group")
    if sender_id is None:
        logger.error("Message missing sender")
    if sender_group is None:
        logger.error("Message missing sender group")
    if sender_id == CLIENT_ID or sender_group == "simulator":
        # Ignore simulator messages
        return

    logger.info(f"MQTT Message Received on {msg.topic}")
    payload = cast(bytes, msg.payload)  # to avoid linter warnings
    try:
        payload = json.loads(payload.decode())
    except UnicodeDecodeError as e:
        logger.exception(f"Error decoding payload: {e.reason}")
        return

    # Extract device_id from topic: expected format nadavnv-smart-home/devices/<device_id>/<method> or similar
    topic_parts = msg.topic.split('/')
    if len(topic_parts) == 4:
        device_id = topic_parts[2]
        method = topic_parts[-1]
        match method:
            case "update":
                if device_id in devices:
                    success, reasons = validate_device_data(payload, device_type=devices[device_id].type)
                    if success:
                        devices[device_id].update(payload)
                        return
                    else:
                        logger.error(f"Failed to update device, reasons: {reasons}")
                logger.error(f"Device ID {device_id} not found")
                return
            case "post":
                success, reasons = validate_device_data(payload, new_device=True)
                if success:
                    create_device(device_data=payload)
                    return
                else:
                    logger.error(f"Failed to create device, reasons: {reasons}")
            case "delete":
                if device_id in devices:
                    devices.pop(device_id)
                    logger.info(f"Device {device_id} deleted successfully")
                    return
                logger.error(f"ID {device_id} not found")
                return
            case _:
                logger.error(f"Unknown method: {method}")
                return
    else:
        logger.error(f"Incorrect topic {msg.topic}")


def init_mqtt() -> None:
    """
    Initialize the MQTT client.
    :return: None
    :rtype: None
    """
    global mqtt_client
    mqtt_client = paho.Client(paho.CallbackAPIVersion.VERSION2, protocol=paho.MQTTv5, client_id=CLIENT_ID)
    mqtt_client.on_message = on_message
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_subscribe = on_subscribe

    logger.info(f"Connecting to MQTT broker {BROKER_HOST}:{BROKER_PORT}...")

    mqtt_client.connect_async(BROKER_HOST, BROKER_PORT)
    mqtt_client.loop_start()


def get_mqtt() -> paho.Client:
    """
    Returns the MQTT client if available.

    :return: MQTT client
    :rtype: paho.Client

    :raises: MQTTNotInitializedError If the MQTT client is not initialized.
    """
    if mqtt_client is None:
        raise MQTTNotInitializedError()
    return mqtt_client


def publish_mqtt(device_id: str, update: Mapping[str, Any]) -> None:
    topic = f"{MQTT_TOPIC}/{device_id}"
    properties = Properties(PacketTypes.PUBLISH)
    properties.UserProperty = [("sender_id", CLIENT_ID), ("sender_group", "simulator")]
    payload = json.dumps(update)
    get_mqtt().publish(topic + "/update", payload.encode(), qos=2, properties=properties)
