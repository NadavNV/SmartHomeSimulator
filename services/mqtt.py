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
message_queue: list[Mapping[str, Any]] = []


# TODO: docstrings
def on_connect(client: paho.Client, _userdata, _connect_flags, reason_code: paho.ReasonCode, _properties=None) -> None:
    """
    Function to run after the MQTT client finishes connecting to the broker. Logs the
    connection, updates the 'status' file, and subscribes to the project topic.

    :param paho.Client client: The MQTT client instance for this callback.
    :param _userdata: Unused by this function.
    :param _connect_flags: Unused by this function.
    :param paho.ReasonCode reason_code: The connection reason code received from the broker.
    :param _properties: Unused by this function.
    :return: None
    :rtype: None
    """
    global mqtt_connected
    logger.info(f'CONNACK received with code {reason_code}.')
    if reason_code == 0:
        with open("./status", "a") as file:
            file.write("ready\n")
            mqtt_connected = True
            if message_queue:
                unsent_msgs = []
                for msg in message_queue:
                    info = client.publish(*msg["args"], **msg["kwargs"])
                    if info.rc != 0:
                        unsent_msgs.append(msg)
                message_queue[:] = unsent_msgs
        logger.info("Connected successfully")
        client.subscribe(f"$share/simulator/{MQTT_TOPIC}/#")


def on_disconnect(_client, _userdata, _disconnect_flags, reason_code, _properties=None) -> None:
    """
    Function to run after the MQTT client disconnects. Updates the 'status' file.

    :param _client: Unused by this function.
    :param _userdata: Unused by this function.
    :param _disconnect_flags: Unused by this function.
    :param reason_code: The disconnection reason code possibly received from the broker.
    :type reason_code: paho.ReasonCode
    :param _properties: Unused by this function.
    :return: None
    :rtype: None
    """
    global mqtt_connected
    if reason_code == 0:
        logger.warning(f"Disconnected from broker.")
    else:
        logger.warning(f"Disconnected from broker with reason: {reason_code}")
    mqtt_connected = False
    with open("./status", "w") as file:
        file.write("healthy\n")


def on_message(
        _client: paho.Client,
        _userdata: Any,
        msg: paho.MQTTMessage,
) -> None:
    """
    Receives the published MQTT payloads and updates the local data structure accordingly.

    Validates the device data and updates the data structure if it's valid.

    :param _client: Unused by this function.
    :param _userdata: Unused by this function.
    :param paho.MQTTMessage msg: The MQTT message received from the broker.
    :return: None
    :rtype: None
    """
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
        device_id = topic_parts[-2]
        method = topic_parts[-1]
        match method:
            case "update":
                if "id" in payload and payload["id"] != device_id:
                    logger.error(f"ID mismatch: ID in URL: {device_id}, ID in payload: {payload['id']}")
                    return
                if device_id in devices:
                    success, reasons = validate_device_data(payload, device_type=devices[device_id].type)
                    if success:
                        devices[device_id].update(payload)
                        logger.info(f"Device {device_id} updated successfully")
                    else:
                        logger.error(f"Failed to update device, reasons: {reasons}")
                else:
                    logger.error(f"Device ID {device_id} not found")
            case "post":
                if "id" in payload and payload["id"] != device_id:
                    logger.error(f"ID mismatch: ID in URL: {device_id}, ID in payload: {payload['id']}")
                    return
                success, reasons = validate_device_data(payload, new_device=True)
                if success:
                    create_device(device_data=payload)
                else:
                    logger.error(f"Failed to create device, reasons: {reasons}")
            case "delete":
                if device_id in devices:
                    devices.pop(device_id)
                    logger.info(f"Device {device_id} deleted successfully")
                else:
                    logger.error(f"Device ID {device_id} not found")
            case _:
                logger.error(f"Unknown method: {method}")
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


def is_mqtt_connected() -> bool:
    """
    Check if the MQTT client is currently connected.

    :return: True if connected, False otherwise
    :rtype: bool
    """
    return mqtt_connected


def publish_mqtt(device_id: str, update: Mapping[str, Any]) -> None:
    """
    Publishes an update message over MQTT so the backend can update the database.

    The simulator only updates existing devices, never deletes or creates new ones.

    :param device_id: The ID of the device to update.
    :type device_id: str
    :param update: The details of the parameters to update.
    :type update: Mapping[str, Any]
    :return: None
    :rtype: None
    """
    topic = f"{MQTT_TOPIC}/{device_id}/update"
    properties = Properties(PacketTypes.PUBLISH)
    properties.UserProperty = [("sender_id", CLIENT_ID), ("sender_group", "simulator")]
    payload = json.dumps(update)
    message = {
        "args": [topic, payload.encode("utf-8")],
        "kwargs": {
            "qos": 2,
            "properties": properties,
        },
    }
    try:
        info = get_mqtt().publish(*message["args"], **message["kwargs"])
        if info.rc != 0:
            if info.rc == 4:  # MQTT_ERR_NO_CONN
                logger.error("Trying to publish on disconnected client.")
            else:
                logger.error(f"Error trying to publish, reason code: {info.rc}.")
            message_queue.append(message)
    except MQTTNotInitializedError:
        logger.error("Trying to publish with uninitialized MQTT")
        message_queue.append(message)
