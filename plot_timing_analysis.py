import pickle
import matplotlib.pyplot as plt

from numpy.polynomial import Polynomial
import numpy as np

def main():
    pkl_file = "/home/benni/datasets/timing_experiment/perceivesemantix/kujiale_0004/kujiale_0004_explore-2/timer_logs.pkl"
    pkl_file = "/home/benni/datasets/timing_experiment/perceivesemantix/kujiale_0004/kujiale_0004_explore-2-cpu/timer_logs.pkl"
    with open(pkl_file, 'rb') as f:
        data = pickle.load(f)

    timestamps = sorted(data["scene_update"].keys())
    proccesing_intervals = [data["scene_update"][ts][0] for ts in timestamps]
    num_objects = [data["scene_update"][ts][1] for ts in timestamps]

    # exclude the first step
    timestamps = np.array(timestamps[1:])
    timestamps -= timestamps[0]
    proccesing_intervals = np.array(proccesing_intervals[1:])
    num_objects = np.array(num_objects[1:])
    actual_intervals = np.diff(timestamps, prepend=timestamps[0])


    # simple plot of intervals over time
    fig, ax1 = plt.subplots()
    color = 'tab:blue'
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Scene Update Interval (s)', color=color)
    ax1.plot(timestamps, proccesing_intervals, color=color)
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.plot(timestamps, actual_intervals, color='tab:green', linestyle='--', label='Actual Interval')
    ax1.legend()


    # plot number of objects on second y axis
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Number of Objects', color=color)
    ax2.plot(timestamps, num_objects, color=color)
    ax2.tick_params(axis='y', labelcolor=color)


    # plot number of objects against intervals
    # sort by num_objects
    sorted_data = sorted(zip(num_objects, proccesing_intervals))
    fig2, ax3 = plt.subplots()
    ax3.set_xlabel('Number of Objects')
    ax3.set_ylabel('Scene Update Interval (s)')
    ax3.plot([d[0] for d in sorted_data], [d[1] for d in sorted_data])

    # fit a curve to the data
    num_objects_array = np.array([d[0] for d in sorted_data])
    intervals_array = np.array([d[1] for d in sorted_data])
    p = Polynomial.fit(num_objects_array, intervals_array, 3)
    x_fit = np.linspace(min(num_objects_array), max(num_objects_array), 100)
    y_fit = p(x_fit)
    ax3.plot(x_fit, y_fit, color='red', label='Fitted Curve')
    ax3.legend()

    plt.show()

if __name__ == "__main__":
    main()