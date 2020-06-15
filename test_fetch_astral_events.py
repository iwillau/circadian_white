import logging
from homeassistant.util import dt as dt_util
from datetime import timedelta
from csv import writer
import matplotlib.pyplot as plt


_LOGGER = logging.getLogger(__name__)


if __name__ == '__main__':
    from custom_components.circadian_white.sensor import CircadianWhiteSensor
    # When to simulate
    dt_util.set_default_time_zone(
        dt_util.get_time_zone('Australia/Melbourne'))

    now = dt_util.now()
    day_start = now.replace(hour=7, minute=1, second=42)
    day_middle = now.replace(hour=12, minute=19, second=32)
    day_end = now.replace(hour=17, minute=37, second=26)

    circ = CircadianWhiteSensor('test_math', 2500, 4500, 6500, 2, 3)

    for offset in range(24):
        print("Offset {}".format(offset))
        test_now = now.replace(hour=offset, minute=0, second=0)

        circ._calculate_day_events(test_now, day_start, day_middle, day_end)
        print(circ._day_start)
        print(day_start)
        print(circ._day_middle)
        print(day_middle)
        print(circ._day_end)
        print(day_end)
        assert(circ._day_start==day_start)
        assert(circ._day_middle==day_middle)
        assert(circ._day_end==day_end+timedelta(minutes=30))

