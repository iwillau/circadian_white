import logging
from homeassistant.util import dt as dt_util
from datetime import timedelta
from csv import writer
import matplotlib.pyplot as plt


_LOGGER = logging.getLogger(__name__)

TOP_EXPONENT=2
BOTTOM_EXPONENT=2.2


if __name__ == '__main__':
    from custom_components.circadian_white.sensor import CircadianWhiteSensor
    # When to simulate
    dt_util.set_default_time_zone(
        dt_util.get_time_zone('Australia/Melbourne'))
    now = dt_util.now()
    day_start = now.replace(hour=7, minute=1, second=42)
    day_middle = now.replace(hour=12, minute=19, second=32)
    day_end = now.replace(hour=17, minute=37, second=26)
    start = now.replace(hour=0, minute=0, second=0)

    def one_day():
        circ = CircadianWhiteSensor('test_math', 2500, 4500, 6500, TOP_EXPONENT, BOTTOM_EXPONENT)
        circ._x_limit = 2
        circ._day_start = day_start
        circ._day_middle = day_middle
        circ._day_end = day_end
        circ._last_sun_update = start
        circ._calculate_day_events()
        print("Sensor Current Config:")
        print(circ.device_state_attributes)
        state = None
        tod = None
        for seconds in range(86399):
            now = start + timedelta(seconds=seconds)
            circ._calculate_kelvins(now)
            if state != circ.state or tod != circ._currently:
                state = circ.state
                tod = circ._currently
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

        plt.yticks([1500, 2500, 4500, 6000, 6500])
        plt.ylim([1000, 7000])
        plt.ylabel('Kelvins')

        ax.set_xlim([0, 86400])
        ax.set_xticks(plot_xticks)
        ax.set_xticklabels(plot_xlabels)

        plt.title("Circadian White level for a sample Day")
        plt.plot(plot_times, plot_kelvins)

        plt.vlines(plot_tod['times'], 0, plot_tod['kelvins'], colors='grey')

        # plt.annotate(xy=[0,6000], s="6000")
        # plt.axhline(y=6000)
        plt.axhline(y=2500)

        fig.text(0.8, 0.4, 
            'Top Exponent: {}\nBottom Exponent: {}'.format(TOP_EXPONENT, BOTTOM_EXPONENT),
            ha='center')

    plt.show()
    fig.clear()
    plt.close(fig)


