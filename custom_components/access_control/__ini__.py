"""Custom integration for managing access control readers and UIDs."""
import json
import logging
import voluptuous as vol
from homeassistant.helpers.storage import Store
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.entity import Entity
from homeassistant.components.mqtt import subscription
from .const import DOMAIN, DATA_KEY, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

# Schema for configuration
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({})},
    extra=vol.ALLOW_EXTRA,
)

# Schema for services
ADD_READER_SCHEMA = vol.Schema(
    {
        vol.Required("reader_id"): str,
        vol.Required("name"): str,
    }
)

ADD_UID_SCHEMA = vol.Schema(
    {
        vol.Required("reader_id"): str,
        vol.Required("uid"): str,
        vol.Required("name"): str,
        vol.Required("surname"): str,
        vol.Optional("allowed", default=False): bool,
    }
)

TOGGLE_UID_SCHEMA = vol.Schema(
    {
        vol.Required("reader_id"): str,
        vol.Required("uid"): str,
    }
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Access Control integration."""
    hass.data[DATA_KEY] = AccessControlData(hass)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigType) -> bool:
    """Set up Access Control from a config entry."""
    data: AccessControlData = hass.data[DATA_KEY]
    await data.async_load()

    # Register services
    async def handle_add_reader(call: ServiceCall):
        await data.async_add_reader(call.data["reader_id"], call.data["name"])

    async def handle_add_uid(call: ServiceCall):
        await data.async_add_uid(
            call.data["reader_id"],
            call.data["uid"],
            call.data["name"],
            call.data["surname"],
            call.data.get("allowed", False),
        )

    async def handle_toggle_uid(call: ServiceCall):
        await data.async_toggle_uid(call.data["reader_id"], call.data["uid"])

    hass.services.async_register(
        DOMAIN, "add_reader", handle_add_reader, schema=ADD_READER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_uid", handle_add_uid, schema=ADD_UID_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "toggle_uid", handle_toggle_uid, schema=TOGGLE_UID_SCHEMA
    )

    # Subscribe to MQTT topics
    await subscription.async_subscribe_topics(
        hass,
        hass.data[DATA_KEY].async_mqtt_message_received,
        [(f"{DOMAIN}/reader/#", 0)],
    )

    return True

class AccessControlData:
    """Class to manage access control data."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.readers = {}  # Format: {reader_id: {"name": str, "uids": {uid: {"name": str, "surname": str, "allowed": bool}}}}

    async def async_load(self):
        """Load data from storage."""
        data = await self.store.async_load()
        if data is not None:
            self.readers = data
        _LOGGER.info("Access Control data loaded: %s", self.readers)

    async def async_save(self):
        """Save data to storage."""
        await self
