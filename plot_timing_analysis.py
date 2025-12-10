import pickle
import matplotlib.pyplot as plt

from numpy.polynomial import Polynomial
import numpy as np
from collections import defaultdict

def main():
    plt.rcParams.update({
            "text.usetex": True,
            "font.size": 8,
            "mathtext.fontset" : "stix",
            "font.family" : "STIXGeneral",
            "mathtext.fontset" : "cm",
            "text.latex.preamble" : r"\usepackage{amsmath}\usepackage{amssymb}",
        })
    
    pkl_files = ["/home/benni/datasets/timing_experiment/perceivesemantix/kujiale_0004/kujiale_0004_explore-2/timer_logs.pkl",
                 "/home/benni/datasets/timing_experiment/perceivesemantix/kujiale_0004/kujiale_0004_explore-3/timer_logs.pkl"]
    # pkl_file = "/home/benni/datasets/timing_experiment/perceivesemantix/kujiale_0004/kujiale_0004_explore-2-cpu/timer_logs.pkl"

    all_timestamps = []
    all_processing_intervals = []
    all_num_objects = []

    for pkl_file in pkl_files:
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

    all_timestamps.extend(timestamps)
    all_processing_intervals.extend(proccesing_intervals)
    all_num_objects.extend(num_objects)


    # simple plot of intervals over time
    cm2inch = 1/2.54
    fig, ax1 = plt.subplots(figsize=(6*cm2inch,5*cm2inch))
    color = 'tab:blue'
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Update Interval (s)', color=color)
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
    sorted_data = sorted(zip(all_num_objects, all_processing_intervals))

    # average intervals for each number of objects
    by_num_objects = defaultdict(list)
    for num_obj, interval in sorted_data:
        by_num_objects[num_obj].append(interval)
    sorted_data = [(num_obj, np.mean(intervals), np.std(intervals)) for num_obj, intervals in sorted(by_num_objects.items())]



    fig2, ax3 = plt.subplots(figsize=(2.75*cm2inch,2*cm2inch))
    ax3.set_xlabel('Number of Objects')
    ax3.set_ylabel('Period (s)')
    # plot with std region
    num_objects_array = np.array([d[0] for d in sorted_data])
    intervals_array = np.array([d[1] for d in sorted_data])
    std_array = np.array([d[2] for d in sorted_data])
    ax3.plot(num_objects_array, intervals_array, color='blue', label='Average Interval', lw=0.75)
    ax3.fill_between(num_objects_array, intervals_array - std_array, intervals_array + std_array, color='blue', alpha=0.2, label='Std Dev')

    # fit a curve to the data
    num_objects_array = np.array([d[0] for d in sorted_data])
    intervals_array = np.array([d[1] for d in sorted_data])
    p = Polynomial.fit(num_objects_array, intervals_array, 2)
    x_fit = np.linspace(min(num_objects_array), max(num_objects_array), 100)
    y_fit = p(x_fit)
    # ax3.plot(x_fit, y_fit, color='red', label='Fitted Curve')
    # ax3.legend()

    fig2.savefig("timing_analysis_plot.pdf", bbox_inches='tight')



    # plt.show()

if __name__ == "__main__":
    main()