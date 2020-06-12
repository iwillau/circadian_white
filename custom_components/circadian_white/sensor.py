"""Support for circadian white sensor."""
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_STATE_CHANGED,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.components.sun import (
    ENTITY_ID as SUN_ENTITY_ID,
    STATE_ATTR_NEXT_DAWN,
    STATE_ATTR_NEXT_DUSK,
    STATE_ATTR_NEXT_NOON,
)

SCAN_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

ATTR_MAX = "max"
ATTR_MIN = "min"
ATTR_MID = "mid"

STATE_ATTR_DAY_START = "day_start"
STATE_ATTR_DAY_MIDDLE = "day_middle"
STATE_ATTR_DAY_END = "day_end"
STATE_ATTR_CURRENTLY = "currently"

DEFAULT_NAME = "Circadian White"

ICON = "mdi:web-clock"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(ATTR_MAX, default=6500): cv.positive_int,
        vol.Optional(ATTR_MIN, default=1500): cv.positive_int,
        vol.Optional(ATTR_MID, default=4500): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Circadian White Entity."""
    async_add_entities([CircadianWhiteSensor(config.get(CONF_NAME),
                                             config.get(ATTR_MIN), 
                                             config.get(ATTR_MID), 
                                             config.get(ATTR_MAX)
                                            )], True)


class CircadianWhiteSensor(Entity):
    """Update a sensor with a circadian white level"""

    def __init__(self, name, minimum, middle, maximum):
        """Initialize the Random sensor."""
        self._name = name
        self._minimum = minimum
        self._middle = middle
        self._maximum = maximum
        self._unit_of_measurement = 'kelvins'
        self._day_start = None
        self._day_end = None
        self._day_middle = None
        self._currently = None
        self._last_sun_update = None
        self._state = self._maximum
        self._available = False

    async def async_added_to_hass(self): 

        @callback
        def update_config(event):
            self.update_sun_events(dt_util.now())
        update_config(None)
        self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, update_config)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Not available if we don't have Sun data"""
        return self._available

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the attributes of the sensor."""
        return {STATE_ATTR_DAY_START: self._day_start.isoformat(),
                STATE_ATTR_DAY_MIDDLE: self._day_middle.isoformat(),
                STATE_ATTR_DAY_END: self._day_end.isoformat(),
                ATTR_MAX: self._maximum, 
                ATTR_MIN: self._minimum,
                ATTR_MID: self._middle,
                STATE_ATTR_CURRENTLY: self._currently}

    async def async_update(self):
        """Calculate where we are in the current day, the day follows the following sequence:
              - Night
              - Early Morning 
              - Mid Morning
              - Late Morning
              - Early Afternoon
              - Mid Afternoon
              - Late Afternoon
              - Evening
              - Night
        """
        if self._last_sun_update is None:
            self._available = False
            _LOGGER.info("Circadian White is still waiting for an update from the Sun")
            return

        now = dt_util.now()
        # If we haven't been updated for more than 24 hours -> bail
        if (now - self._last_sun_update).days > 0:
            self._available = False
            _LOGGER.warn("Astral data is out of date")
            return


        gap = timedelta(hours=2)

        if now < self._day_start:
            self._currently = 'Night'
            self._state = self._minimum
        elif now < (self._day_start + gap):
            self._currently = 'Early Morning'
            self._calc_progress(self._minimum, self._middle, gap.seconds, (now - self._day_start).seconds)
        elif now < (self._day_middle - gap):
            self._currently = 'Mid Morning'
            self._state = self._middle
        elif now < (self._day_middle):
            self._currently = 'Late Morning'
            self._calc_progress(self._middle, self._maximum, gap.seconds, (now - self._day_middle + gap).seconds)
        elif now < (self._day_middle + gap):
            self._currently = 'Early Afternoon'
            self._calc_progress(self._maximum, self._middle, gap.seconds, (now - self._day_middle).seconds)
        elif now < (self._day_end - gap):
            self._currently = 'Mid Afternoon'
            self._state = self._middle
        elif now < (self._day_end):
            self._currently = 'Late Afternoon'
            self._calc_progress(self._middle, self._minimum, gap.seconds, (now - self._day_end + gap).seconds)
        elif now < (self._day_end + gap):
            self._currently = 'Evening'
        else:
            self._currently = 'Night'
            self._state = self._minimum

        _LOGGER.info("Day is currently: {}".format(self._currently))

    def _calc_progress(self, start, end, length, progress):
        m_length = end - start  # Actual Length of the Metric (kelvins)
        percentage_complete = progress / length  # Perc
        m_progress = percentage_complete * m_length
        self._state = int(m_progress+start)
      
    @callback
    def update_sun_events(self, point_in_time):
        _LOGGER.debug("Updating Astral Events from Sun Entity")
        sun = self.hass.states.get(SUN_ENTITY_ID)
        if sun is None:
            _LOGGER.warn("Can't access the Sun Entity, try again in 5 minutes")
            async_track_point_in_time(
                self.hass, self.update_sun_events, point_in_time + timedelta(minutes=5)
            )
            return

        self._day_start = dt_util.as_local(dt_util.parse_datetime(sun.attributes[STATE_ATTR_NEXT_DAWN]))
        self._day_middle = dt_util.as_local(dt_util.parse_datetime(sun.attributes[STATE_ATTR_NEXT_NOON]))
        self._day_end = dt_util.as_local(dt_util.parse_datetime(sun.attributes[STATE_ATTR_NEXT_DUSK]))

        # If we're bootstrapping for any reason, the times will be in the future, small error, but we'll just set them to today
        today = point_in_time.date()

        if today != self._day_start.date():
            self._day_start = self._day_start - timedelta(days=1)
        if today != self._day_middle.date():
            self._day_middle = self._day_middle - timedelta(days=1)
        if today != self._day_end.date():
            self._day_end = self._day_end - timedelta(days=1)
        
        self._last_sun_update = point_in_time
        # self._available = True
        self.async_write_ha_state()

        schedule = self._day_end + timedelta(hours=3)
        if point_in_time > schedule:
            schedule = self._day_end + timedelta(hours=27)
        
        _LOGGER.debug("Scheduling next astral for: {}".format(schedule))
        async_track_point_in_time(self.hass, self.update_sun_events, schedule)


