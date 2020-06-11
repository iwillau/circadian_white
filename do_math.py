import logging
from homeassistant.util import dt as dt_util
from datetime import timedelta
from csv import writer


_LOGGER = logging.getLogger(__name__)


dt_util.set_default_time_zone(dt_util.get_time_zone('Australia/Melbourne'))


class CircadianWhiteSensor():

    def __init__(self, minimum, middle, maximum):
        """Initialize the Random sensor."""
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
    
        now = dt_util.now()
        self._day_start = now.replace(hour=7, minute=1, second=42)
        self._day_middle = now.replace(hour=12, minute=19, second=32)
        self._day_end = now.replace(hour=17, minute=37, second=26)
        self._last_sun_update = now

    @property
    def state(self):
        """Return the state of the device."""
        return self._state


    def update(self):
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

        self._calculate_kelvins(now)
        _LOGGER.info("Day is currently: {}".format(self._currently))
        
    def _calculate_kelvins(self, now):

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

    def _calc_progress(self, start, end, length, progress):
        m_length = end - start  # Actual Length of the Metric (kelvins)
        percentage_complete = progress / length  # Perc
        m_progress = percentage_complete * m_length
        self._state = int(m_progress+start)


if __name__ == '__main__':
    circ = CircadianWhiteSensor(1500, 4500, 6500)

    def one_day():
        start = dt_util.now().replace(hour=0, minute=0, second=0)
        for seconds in range(86400):
            yield start + timedelta(seconds=seconds)


    with open('sample_day.csv', 'w', newline='') as file_h:
        csv = writer(file_h)
        csv.writerow(['Date', 'Time', 'Time of Day', 'Second', 'Kelvins'])
        tod = None
        state = None
        for now in one_day():
            circ._calculate_kelvins(now)
            if state != circ.state:
                state = circ.state
                csv.writerow([now.date(), now.strftime("%H:%M"), 
                              circ._currently, now.second, circ.state])
                          
            if tod != circ._currently:
                tod = circ._currently
                print("{} {:16} -> {}".format(now.strftime("%H:%M:%S"), tod, circ.state))
                
            


