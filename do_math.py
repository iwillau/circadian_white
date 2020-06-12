import logging
from homeassistant.util import dt as dt_util
from datetime import timedelta
from csv import writer
import matplotlib.pyplot as plt


_LOGGER = logging.getLogger(__name__)


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
    # When to simulate
    dt_util.set_default_time_zone(
        dt_util.get_time_zone('Australia/Melbourne'))
    now = dt_util.now()
    day_start = now.replace(hour=7, minute=1, second=42)
    day_middle = now.replace(hour=12, minute=19, second=32)
    day_end = now.replace(hour=17, minute=37, second=26)
    start = now.replace(hour=0, minute=0, second=0)

    def one_day():
        circ = CircadianWhiteSensor(1500, 4500, 6500)
        circ._day_start = day_start
        circ._day_middle = day_middle
        circ._day_end = day_end
        circ._last_sun_update = start
        
        state = None
        for seconds in range(86399):
            now = start + timedelta(seconds=seconds)
            circ._calculate_kelvins(now)
            if state != circ.state:
                state = circ.state
                yield seconds, now, circ
        #Yield the final state no matter what
        now = start + timedelta(seconds=86400)
        circ._calculate_kelvins(now)
        yield 86400, now, circ
        
    plot_times = []
    plot_kelvins = []
    plot_tod = {
        'times': [],
        'kelvins': [],
    }
    plot_xticks = [0,
                   (day_start - start).total_seconds(),
                   (day_middle - start).total_seconds(),
                   (day_end - start).total_seconds(),
                   86400]
    plot_xlabels = ['Midnight', 
                    'Dawn',
                    'Noon',
                    'Dusk', 
                    'Midnight']
    with open('sample_day.csv', 'w', newline='') as file_h:
        csv = writer(file_h)
        csv.writerow(['Date', 'Time', 'Time of Day', 'Second', 'Kelvins'])
        tod = None

        for seconds, now, circ in one_day():
            csv.writerow([now.date(), now.strftime("%H:%M"), 
                          circ._currently, now.second, circ.state])
            plot_times.append(seconds)
            plot_kelvins.append(circ.state)
            
            if tod != circ._currently:
                tod = circ._currently
                plot_tod['times'].append(seconds)
                plot_tod['kelvins'].append(circ.state)
                print("{} {:16} -> {}".format(
                    now.strftime("%H:%M:%S"), tod, circ.state))
    
    with plt.xkcd():
        fig = plt.figure()
        
        ax = fig.add_axes((0.1, 0.1, 0.8, 0.8))
        ax.xaxis.set_ticks_position('bottom')
        ax.yaxis.set_ticks_position('left')
        ax.spines['right'].set_color('none')
        ax.spines['top'].set_color('none')
        
        plt.yticks([1500, 4500, 6500])
        plt.ylim([1000, 7000])
        plt.ylabel('Kelvins')
        
        ax.set_xlim([0, 86400])
        ax.set_xticks(plot_xticks)
        ax.set_xticklabels(plot_xlabels)
        
        plt.title("Circadian White level for a sample Day")
        plt.plot(plot_times, plot_kelvins)

        plt.vlines(plot_tod['times'], 0, plot_tod['kelvins'], colors='grey')
        
    plt.show()
    fig.clear()
    plt.close(fig)
                

