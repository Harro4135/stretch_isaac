from pathlib import Path
import json
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np


def select_experiments(
    data,
    app_name: list[str] = [],
    name_filter: list[str] = [],
    exclusive_name: list[str] = [],
    success: Optional[bool] = None,
):
    if isinstance(app_name, str):
        app_name = [app_name]
    if app_name:
        data = [exp for exp in data if exp["app"] in app_name]
    if name_filter:
        data = [exp for exp in data if any(nf in exp["experiment"]["name"] for nf in name_filter)]
    if exclusive_name:
        data = [exp for exp in data if all(en not in exp["experiment"]["name"] for en in exclusive_name)]
    if success is not None:
        data = [exp for exp in data if exp["success"] == success]
    return data


def load_result_json(file_path: Path):
    # Load data from .json file
    with open(file_path, "r") as f:
        data = json.load(f)

    for exp in data:
        if exp["app"] != "genmap" and exp["path_length"] < 1.0:
            print(f"Warning: Experiment {exp['name']} has path length {exp['path_length']}")
    return data


def get_genmap_outfile(experiments: dict, experiment_name: str) -> Optional[str]:
    map_file = None
    for exp in experiments:
        if exp["app"] == "genmap" and exp["experiment"]["name"] == experiment_name:
            map_file = exp["log_files"][0]
            break
    if not map_file:
        print(f"Genmap output file for experiment '{experiment_name}' not found.")
    return map_file


def create_experiment_plot(experiment_result: dict, all_experiments: dict, figsize=(8, 8)):
    experiment_name = experiment_result["experiment"]["name"]
    map_file = get_genmap_outfile(all_experiments, experiment_name)
    if not map_file:
        return
    # map file is a .npz file  with colored_map, x, y, goal_positions, shortest_path
    map_data = np.load(map_file)
    colored_map = map_data["colored_map"] if "colored_map" in map_data else map_data["occupancy_map"]
    x = map_data["x"]
    y = map_data["y"]
    goal_positions = map_data["goal_positions"] if "goal_positions" in map_data else np.ndarray((0, 2))
    shortest_path = map_data["shortest_path"] if "shortest_path" in map_data else np.ndarray((0, 2))

    mask = np.any(colored_map != 1.0, axis=2)  # True where any channel is not 1.0
    rows, cols = np.where(mask)

    # minimal indices
    r0, r1 = rows.min(), rows.max()
    c0, c1 = cols.min(), cols.max()

    # convert to coordinates (indexing='ij')
    min_x, max_x = x[r0], x[r1]
    min_y, max_y = y[c0], y[c1]

    # ensure proper ordering
    min_x, max_x = min(min_x, max_x), max(min_x, max_x)
    min_y, max_y = min(min_y, max_y), max(min_y, max_y)

    # make square
    width_x = max_x - min_x
    width_y = max_y - min_y
    width = max(width_x, width_y)

    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    min_x, max_x = mid_x - width / 2, mid_x + width / 2
    min_y, max_y = mid_y - width / 2, mid_y + width / 2

    cm_2inch = 1 / 2.54

    fig = plt.figure(figsize=(figsize[0] * cm_2inch, figsize[1] * cm_2inch))
    X, Y = np.meshgrid(x, y, indexing="ij")

    colored_map[mask] *= 0.8
    plt.pcolormesh(X, Y, colored_map, shading="auto", rasterized=True)

    state_trajectory_file = experiment_result["state_trajectory_file"]
    state_trajecory = np.load(state_trajectory_file)
    # state trajectory is like N x 10 array with time, pos(x,y,z), ori(x,y,z,w), vel(x,y,z)

    plt.plot(state_trajecory[:, 1], state_trajecory[:, 2], color="gray", ls="-", label="Robot Path")
    plt.scatter(state_trajecory[0, 1], state_trajecory[0, 2], color="gray", s=50, label="Start")
    plt.scatter(goal_positions[:, 0], goal_positions[:, 1], color="orange", marker="*", s=100, label="Goal Positions")
    # plt.plot(shortest_path[:,0], shortest_path[:,1], color='gray', linestyle=':', label='Shortest Path')

    success = experiment_result["success"]

    text = experiment_result["experiment"]["goal"]["label"] + ":" + f" {'found' if success else 'not found'}\n"
    plt.text(
        0.5,
        0.98,
        text,
        transform=plt.gca().transAxes,
        verticalalignment="top",
        horizontalalignment="center",
        fontsize=10,
    )

    # plt.xlabel('X (m)')
    # plt.ylabel('Y (m)')

    plt.xticks([])
    plt.yticks([])

    # plt.title(f'Experiment: {experiment_name}, Success: {success}')
    plt.axis("equal")
    print(min_x, max_x, min_y, max_y)
    plt.xlim(min_x, max_x)
    plt.ylim(min_y, max_y)
    # plt.legend()

    return fig


def main():
    """
    Generate publication-quality plots for hidden object search experiments.
    1. Load experiment results from a JSON file.
    2. Filter experiments based on application names and name criteria.
    3. For each selected experiment, create a plot visualizing the robot's trajectory and environment map.
    4. Save each plot as a PDF in the specified output directory.
    """
    data = load_result_json("/home/benni/datasets/sim_results_syn_new/experiments_results.json")

    exp = select_experiments(
        data, app_name=["dynamem", "perceivesemantix", "random"], name_filter=["hidden"], exclusive_name=["explore"]
    )
    fig_output_dir = Path("/home/benni/datasets/sim_results_syn_new/plots-ready/hidden")
    fig_output_dir.mkdir(parents=True, exist_ok=True)

    for e in exp:
        if "knife" not in e["experiment"]["name"]:
            continue
        fig = create_experiment_plot(e, data, figsize=(7, 7))
        if fig:
            fig.savefig(fig_output_dir / f"{e['name']}.pdf")
            plt.close(fig)


if __name__ == "__main__":
    main()
