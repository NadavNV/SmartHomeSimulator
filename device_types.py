from enum import auto, StrEnum


class DeviceType(StrEnum):
    WATER_HEATER = auto()
    LIGHT = auto()
    AIR_CONDITIONER = auto()
    DOOR_LOCK = auto()
    CURTAIN = auto()