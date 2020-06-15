"""Support for circadian white sensor."""
import logging
from datetime import datetime, timedelta
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
ATTR_TOP_EXPONENT = "top_exponent"
ATTR_BOTTOM_EXPONENT = "bottom_exponent"

STATE_ATTR_DAY_START = "day_start"
STATE_ATTR_DAY_MIDDLE = "day_middle"
STATE_ATTR_DAY_END = "day_end"
STATE_ATTR_CURRENTLY = "time_of_day"

DEFAULT_NAME = "Circadian White"

ICON = "mdi:web-clock"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(ATTR_MAX, default=6500): cv.positive_int,
        vol.Optional(ATTR_MIN, default=2500): cv.positive_int,
        vol.Optional(ATTR_MID, default=4500): cv.positive_int,
        vol.Optional(ATTR_TOP_EXPONENT, default=2): vol.All(vol.Coerce(int), vol.Range(min=1, min_included=False)),
        vol.Optional(ATTR_BOTTOM_EXPONENT, default=2.2): vol.All(vol.Coerce(int), vol.Range(min=1, min_included=False)),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Circadian White Entity."""
    async_add_entities([CircadianWhiteSensor(config.get(CONF_NAME),
                                             config.get(ATTR_MIN),
                                             config.get(ATTR_MID),
                                             config.get(ATTR_MAX),
                                             config.get(ATTR_TOP_EXPONENT),
                                             config.get(ATTR_BOTTOM_EXPONENT),
                                            )], True)


class CircadianWhiteSensor(Entity):
    """Update a sensor with a circadian white level"""

    def __init__(self, name, minimum, middle, maximum, top_exponent, bottom_exponent):
        """Initialize the Random sensor."""
        self._name = name
        self._overnight = 1500
        self._minimum = minimum
        self._middle = middle
        self._maximum = maximum
        self._unit_of_measurement = 'kelvins'
        self._day_start = None
        self._day_middle = None
        self._day_end = None
        self._currently = None
        self._last_sun_update = None
        self._state = self._maximum
        self._available = False
        
        # Math Variables. Only the exponent is exposed to the user
        # But they could all be changed for varied results.
        # Utilised do_math to see the results.
        self._x_limit = 2
        self._top_exponent = top_exponent
        self._bottom_exponent = bottom_exponent
        self._update_formula()

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
                ATTR_TOP_EXPONENT: self._top_exponent,
                ATTR_BOTTOM_EXPONENT: self._bottom_exponent,
                STATE_ATTR_CURRENTLY: self._currently}

    async def async_update(self):
        """Calculate where we are in the current day, the day follows the following sequence:
              - Night
              - Early Morning
              - Late Morning
              - Early Afternoon
              - Late Afternoon
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

        self._calculate_kelvins(now)
        _LOGGER.info("Day is currently: {}".format(self._currently))

    def _calculate_kelvins(self, now):
        self._state = self._minimum
        if now < self._predawn:
            self._currently = 'Night'
            self._state = self._overnight
        elif now < self._day_start:
            self._currently = 'Pre-Dawn'
            progress = (now - self._predawn).seconds/3600  # Currently predawn is hardcoded for 1 hour
            curve = self._predawn_a * self._predawn_exponent ** (self._x_limit - (progress * self._x_limit * 2)) + self._predawn_c
            self._state = int(curve)
        elif now < self._mid_morning:
            self._currently = 'Early Morning'
            progress = (now - self._day_start)/self._morning_length
            curve = self._bottom_a * self._bottom_exponent ** ((progress * self._x_limit * 2) - self._x_limit) + self._bottom_c
            self._state = int(curve)
        elif now < self._day_middle:
            self._currently = 'Late Morning'
            progress = (now - self._mid_morning)/self._morning_length
            curve = self._top_a * self._top_exponent ** (self._x_limit - (progress * self._x_limit * 2)) + self._top_c
            self._state = int(curve)
        elif now < self._mid_afternoon:
            self._currently = 'Early Afternoon'
            progress = (now - self._day_middle)/self._afternoon_length
            curve = self._top_a * self._top_exponent ** ((progress * self._x_limit * 2) - self._x_limit) + self._top_c
            self._state = int(curve)
        elif now < self._day_end:
            self._currently = 'Late Afternoon'
            progress = (now - self._mid_afternoon)/self._afternoon_length
            curve = self._bottom_a * self._bottom_exponent ** (self._x_limit - (progress * self._x_limit * 2)) + self._bottom_c
            self._state = int(curve)
        elif now < self._late_evening:
            self._currently = 'Evening'
            progress = (now - self._day_end)/self._evening_length
            curve = self._evening_a * self._evening_exponent ** ((progress * self._x_limit * 2) - self._x_limit) + self._evening_c
            self._state = int(curve)
        elif now < self._nighttime:
            self._currently = 'Late Evening'
            progress = (now - self._day_end)/self._evening_length
            curve = self._evening_a * self._evening_exponent ** ((progress * self._x_limit * 2) - self._x_limit) + self._evening_c
            self._state = int(curve)
        else:
            self._currently = 'Night'
            self._state = self._overnight

    def _update_formula(self):
        """We use the general formula
                a*b^x + c = y
        Where y ends up being the kelvins and x is normalsed from the _x_limit to a percentage of the time
        in the window we are calculating.
        ie. if _x_limit = 2 then the x goes from -2 -> 2 across the time window.

        b is the exponent. By default we use 3 for the early morning and late afternoon (bottom_exponent)
        and 2 for the noon window (top exponent). 
        This gives a gentle wake up curve and then spends less time at the bluest at noon time 
        """
        x = self._x_limit
        b = self._bottom_exponent
        y2 = self._middle
        y1 = self._minimum
        # Calculate the bottom vars first
        self._bottom_a = ( y2 - y1 )/(b ** x - b ** -x)
        self._bottom_c = (( b ** x ) * y1 - (b ** -x) * y2) / ( b ** x - b ** -x)

        # Now the Top vars
        y2 = self._maximum
        y1 = self._middle
        b = self._top_exponent
        self._top_a = ( y2 - y1 )/(b ** -x - b ** x)
        self._top_c = (( b ** -x ) * y1 - (b ** x) * y2) / ( b ** -x - b ** x)

        # Now the predawn vars
        y2 = self._minimum
        y1 = self._overnight
        b = self._predawn_exponent = 2
        self._predawn_a = ( y2 - y1 )/(b ** -x - b ** x)
        self._predawn_c = (( b ** -x ) * y1 - (b ** x) * y2) / ( b ** -x - b ** x)

        # Now the evening vars
        y2 = self._minimum
        y1 = self._overnight
        b = self._evening_exponent = 8
        self._evening_a = ( y2 - y1 )/(b ** -x - b ** x)
        self._evening_c = (( b ** -x ) * y1 - (b ** x) * y2) / ( b ** -x - b ** x)

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

        self._calculate_day_events(
            point_in_time,
            dt_util.as_local(dt_util.parse_datetime(sun.attributes[STATE_ATTR_NEXT_DAWN])),
            dt_util.as_local(dt_util.parse_datetime(sun.attributes[STATE_ATTR_NEXT_NOON])),
            dt_util.as_local(dt_util.parse_datetime(sun.attributes[STATE_ATTR_NEXT_DUSK])),
            )

        self._last_sun_update = point_in_time
        self._available = True
        self.async_write_ha_state()

        schedule = self._nighttime + timedelta(minutes=15)
        if point_in_time > schedule:
            schedule = self._nighttime + timedelta(minutes=15)

        _LOGGER.debug("Scheduling next astral for: {}".format(schedule))
        async_track_point_in_time(self.hass, self.update_sun_events, schedule)


    def _calculate_day_events(self, now, day_start, day_middle, day_end):
        # If we're bootstrapping for any reason, ie, a restart/reload
        # the times will be in the future, small error, but we'll just set them to today
        # unless we are already past the day_end
        today = now.date()
        # Co-erce them all to today. 
        self._day_start = datetime.combine(today, day_start.time(), day_start.tzinfo)
        self._day_middle = datetime.combine(today, day_middle.time(), day_middle.tzinfo)
        self._day_end = datetime.combine(today, day_end.time(), day_end.tzinfo)

        self._predawn = self._day_start - timedelta(hours=1)
        self._morning_length = (self._day_middle - self._day_start)/2
        self._mid_morning = self._day_start + self._morning_length

        self._late_evening = self._day_end + timedelta(hours=1)
        # We don't want late_night to be very far past 10PM
        ten_pm = self._day_end.replace(hour=22, minute=0, second=0)
        while self._late_evening < ten_pm:
            self._late_evening = self._late_evening + timedelta(minutes=15)

        self._nighttime = self._late_evening + timedelta(hours=1)

        # This is a bit of a fallacy. But if dusk is more than 4 hours before late evening
        # We're just going to push it later 1/2 an hour. So that "Evening" is't quite as long a part of the day.
        if (self._late_evening - self._day_end) > timedelta(hours=4):
            self._day_end += timedelta(minutes=30)

        self._evening_length = self._nighttime - self._day_end
        self._afternoon_length = (self._day_end - self._day_middle)/2
        self._mid_afternoon = self._day_middle + self._afternoon_length

