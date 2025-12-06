from pathlib import Path
import json
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

def select_experiments(data, app_name: list[str] = [], name_filter: list[str] = [], exclusive_name: list[str] = [], success: Optional[bool] = None):
    if isinstance(app_name, str):
        app_name = [app_name]
    if app_name:
        data = [exp for exp in data if exp['app'] in app_name]
    if name_filter:
        data = [exp for exp in data if any(nf in exp['experiment']['name'] for nf in name_filter)]
    if exclusive_name:
        data = [exp for exp in data if all(en not in exp['experiment']['name'] for en in exclusive_name)]
    if success is not None:
        data = [exp for exp in data if exp['success'] == success]
    return data

def load_result_json(file_path: Path):
    # Load data from .json file
    with open(file_path, 'r') as f:
        data = json.load(f)

    for exp in data:
        if exp["app"] != "genmap" and exp["path_length"] < 1.0:
            print(f"Warning: Experiment {exp['name']} has path length {exp['path_length']}")
    return data

def compute_spl(shortest_distance: list[float], path_length: list[float], success: list[bool]) -> float:
    spl_values = []
    for sd, pl, suc in zip(shortest_distance, path_length, success):
        if suc:
            sd = max(sd + 1.5, 0.1)  # avoid division by zero
            spl_values.append(sd / max(pl, sd))
        else:
            spl_values.append(0.0)
    return sum(spl_values) / len(spl_values) if spl_values else 0.0

def get_genmap_outfile(experiments: dict, experiment_name: str) -> Optional[str]:
    map_file = None
    for exp in experiments:
        if exp['app'] == 'genmap' and exp['experiment']['name'] == experiment_name:
            map_file = exp['log_files'][0]
            break
    if not map_file:
        print(f"Genmap output file for experiment '{experiment_name}' not found.")
    return map_file

def create_experiment_plot(experiment_result: dict, all_experiments: dict, figsize=(8,8)):
    experiment_name = experiment_result['experiment']['name']
    map_file = get_genmap_outfile(all_experiments, experiment_name)
    if not map_file:
        return
    # map file is a .npz file  with colored_map, x, y, goal_positions, shortest_path
    map_data = np.load(map_file)
    colored_map = map_data["colored_map"] if 'colored_map' in map_data else map_data['occupancy_map']
    x = map_data['x']
    y = map_data['y']
    goal_positions = map_data['goal_positions'] if 'goal_positions' in map_data else np.ndarray((0,2))
    shortest_path = map_data['shortest_path'] if 'shortest_path' in map_data else np.ndarray((0,2))

    fig = plt.figure(figsize=figsize)
    X, Y = np.meshgrid(x, y, indexing='ij')
    plt.pcolormesh(X, Y, colored_map, shading='auto')

    state_trajectory_file = experiment_result["state_trajectory_file"]
    state_trajecory = np.load(state_trajectory_file)
    # state trajectory is like N x 10 array with time, pos(x,y,z), ori(x,y,z,w), vel(x,y,z)

    plt.plot(state_trajecory[:,1], state_trajecory[:,2], color='red', label='Robot Path')
    plt.scatter(state_trajecory[0,1], state_trajecory[0,2], color='green', label='Start')
    plt.scatter(goal_positions[:,0], goal_positions[:,1], color='red', marker='x', label='Goal Positions')
    # plt.plot(shortest_path[:,0], shortest_path[:,1], color='gray', linestyle=':', label='Shortest Path')

    success = experiment_result['success']


    plt.xlabel('X (m)')
    plt.ylabel('Y (m)')
    plt.title(f'Experiment: {experiment_name}, Success: {success}')
    plt.axis('equal')
    plt.legend()

    return fig

def main():

    # Ours
    # data = load_result_json("/home/benni/datasets/sim_results_syn/experiments_results.json")
    data = load_result_json("/home/benni/datasets/sim_results_syn_new/experiments_results.json")
    

    # exp = select_experiments(data, app_name=['dynamem', 'perceivesemantix', 'random'], exclusive_name=['hidden','explore'])
    # fig_output_dir = Path("/home/benni/datasets/sim_results_syn_new/plots/known")
    # fig_output_dir.mkdir(parents=True, exist_ok=True)
    # for e in exp:
    #     fig = create_experiment_plot(e, data)
    #     if fig:
    #         fig.savefig(fig_output_dir / f"{e['name']}.pdf")
    #         plt.close(fig)

    exp = select_experiments(data, app_name=['dynamem', 'perceivesemantix', 'random'], name_filter=['hidden'], exclusive_name=['explore'])
    fig_output_dir = Path("/home/benni/datasets/sim_results_syn_new/plots/hidden")
    fig_output_dir.mkdir(parents=True, exist_ok=True)
    for e in exp:
        fig = create_experiment_plot(e, data)
        if fig:
            fig.savefig(fig_output_dir / f"{e['name']}.pdf")
            plt.close(fig)


    # return

    known_ours_experiments = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore']))
    known_ours_success_rates = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore'], success=True)) / known_ours_experiments if known_ours_experiments > 0 else 0
    known_ours_spl = compute_spl( *zip(*[(exp["goal_shortest_distance"], exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore']) ]))

    novel_ours_experiments = len(select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore']))
    novel_ours_success_rates = len(select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore'], success=True)) / novel_ours_experiments if novel_ours_experiments > 0 else 0
    novel_ours_spl = compute_spl( *zip(*[(exp["goal_shortest_distance"], exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore']) ]))

    # Dynamem
    # data = load_result_json("/home/benni/datasets/sim_results_syn_dynamem/experiments_results.json")
    known_dynamem_experiments = len(select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore']))
    known_dynamem_success_rates = len(select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore'], success=True)) / known_dynamem_experiments if known_dynamem_experiments > 0 else 0
    known_dynamem_spl = compute_spl(*zip(*[(exp["goal_shortest_distance"], exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore'])]))

    novel_dynamem_experiments = len(select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore']))
    novel_dynamem_success_rates = len(select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore'], success=True)) / novel_dynamem_experiments if novel_dynamem_experiments > 0 else 0
    novel_dynamem_spl = compute_spl(*zip(*[(exp["goal_shortest_distance"], exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore'])]))
    # # get expriments where perceivesemantix and dynamem failed
    # failed_experiments_perceivesemantix = select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore'], success=False)
    # failed_experiments_dynamem = select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore'], success=False)
    # common_failed_experiments = set(exp['experiment']['name'] for exp in failed_experiments_perceivesemantix) & set(exp['experiment']['name'] for exp in failed_experiments_dynamem)
    # print(f"Common failed experiments between perceivesemantix and dynamem: {common_failed_experiments}")

    # novel_failed_experiments_perceivesemantix = select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore'], success=False)
    # novel_failed_experiments_dynamem = select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore'], success=False)
    # common_novel_failed_experiments = set(exp['experiment']['name'] for exp in novel_failed_experiments_perceivesemantix) & set(exp['experiment']['name'] for exp in novel_failed_experiments_dynamem)
    # print(f"Common failed novel experiments between perceivesemantix and dynamem: {common_novel_failed_experiments}")

    # common_all_failed_experiments = common_failed_experiments.intersection((exp.removesuffix("-hidden") for exp in common_novel_failed_experiments))
    # print(f"All common failed experiments between perceivesemantix and dynamem: {common_all_failed_experiments}")


    # Random
    known_random_experiments = len(select_experiments(data, app_name='random', exclusive_name=['hidden', 'explore']))
    known_random_success_rates = len(select_experiments(data, app_name='random', exclusive_name=['hidden', 'explore'], success=True)) / known_random_experiments if known_random_experiments > 0 else 0
    known_random_spl = compute_spl( *zip(*[(exp["goal_shortest_distance"], exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='random', exclusive_name=['hidden', 'explore']) ]))
    

    novel_random_experiments = len(select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore']))
    novel_random_success_rates = len(select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore'], success=True)) / novel_random_experiments if novel_random_experiments > 0 else 0
    novel_random_spl = compute_spl( *zip(*[(exp["goal_shortest_distance"], exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore']) ]))


    data = load_result_json("/home/benni/datasets/sim_results_syn_moved/experiments_results.json")
    fig_output_dir = Path("/home/benni/datasets/sim_results_syn_moved/plots/moved")
    fig_output_dir.mkdir(parents=True, exist_ok=True)

    exp = select_experiments(data, app_name=['dynamem', 'perceivesemantix', 'random'], exclusive_name=['explore'])
    for e in exp:
        fig = create_experiment_plot(e, data)
        if fig:
            fig.savefig(fig_output_dir / f"{e['name']}.pdf")
            plt.close(fig)
    return

    for exp in select_experiments(data, app_name='dynamem', exclusive_name=['explore']):
        if "goal_shortest_distance" not in exp:
            if "goal_shortest_distance" not in exp["experiment"]["goal"]:
                print(f"Experiment {exp['name']} missing goal_shortest_distance")


    moved_ours_experiments = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore']))
    moved_ours_success_rates = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore'], success=True)) / moved_ours_experiments if moved_ours_experiments > 0 else 0
    moved_ours_spl = compute_spl( *zip(*[(exp.get("goal_shortest_distance", exp["experiment"]["goal"]["goal_shortest_distance"]), exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore']) ]))

    moved_dynamem_experiments = len(select_experiments(data, app_name='dynamem', exclusive_name=['explore']))
    moved_dynamem_success_rates = len(select_experiments(data, app_name='dynamem', exclusive_name=['explore'], success=True)) / moved_dynamem_experiments if moved_dynamem_experiments > 0 else 0
    moved_dynamem_spl = compute_spl( *zip(*[(exp.get("goal_shortest_distance", exp["experiment"]["goal"].get("goal_shortest_distance")), exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='dynamem', exclusive_name=['explore']) ]))

    moved_random_experiments = len(select_experiments(data, app_name='random', exclusive_name=['explore']))
    moved_random_success_rates = len(select_experiments(data, app_name='random', exclusive_name=['explore'], success=True)) / moved_random_experiments if moved_random_experiments > 0 else 0
    moved_random_spl = compute_spl( *zip(*[(exp.get("goal_shortest_distance", exp["experiment"]["goal"].get("goal_shortest_distance")), exp["path_length"], exp["success"]) for exp in select_experiments(data, app_name='random', exclusive_name=['explore']) ]))

    print("=== Known ===")
    print(f"Dynamem Success Rates {known_dynamem_success_rates:.2f} over {known_dynamem_experiments} trials")
    print(f"Ours Success Rates {known_ours_success_rates:.2f} over {known_ours_experiments} trials")
    print(f"Random Success Rates {known_random_success_rates:.2f} over {known_random_experiments} trials")
    print(f"Dynamem SPL {known_dynamem_spl:.2f}")
    print(f"Ours SPL {known_ours_spl:.2f}")
    print(f"Random SPL {known_random_spl:.2f}")

    print("=== Novel ===")
    print(f"Dynamem Success Rates {novel_dynamem_success_rates:.2f} over {novel_dynamem_experiments} trials")
    print(f"Ours Success Rates {novel_ours_success_rates:.2f} over {novel_ours_experiments} trials")
    print(f"Random Success Rates {novel_random_success_rates:.2f} over {novel_random_experiments} trials")
    print(f"Dynamem SPL {novel_dynamem_spl:.2f}")
    print(f"Ours SPL {novel_ours_spl:.2f}")
    print(f"Random SPL {novel_random_spl:.2f}")

    print("=== Moved ===")
    print(f"Dynamem Success Rates {moved_dynamem_success_rates:.2f} over {moved_dynamem_experiments} trials")
    print(f"Ours Success Rates {moved_ours_success_rates:.2f} over {moved_ours_experiments} trials")
    print(f"Random Success Rates {moved_random_success_rates:.2f} over {moved_random_experiments} trials")
    print(f"Dynamem SPL {moved_dynamem_spl:.2f}")
    print(f"Ours SPL {moved_ours_spl:.2f}")
    print(f"Random SPL {moved_random_spl:.2f}")     


    plt.bar(
        ['Known Dynamem', 'Known Ours', 'Known Random', 'Novel Dynamem', 'Novel Ours', 'Novel Random', 'Moved Dynamem', 'Moved Ours', 'Moved Random'],
        [known_dynamem_success_rates, known_ours_success_rates, known_random_success_rates, novel_dynamem_success_rates, novel_ours_success_rates, novel_random_success_rates, moved_dynamem_success_rates, moved_ours_success_rates, moved_random_success_rates],
        color=['blue', 'orange', 'green', 'blue', 'orange', 'green', 'blue', 'orange', 'green']
    )
    plt.ylim(0, 1)
    plt.ylabel('Success Rate')
    plt.title('Simulation Success Rates')


    # second plot for spl
    plt.figure()
    plt.bar(
        ['Known Dynamem', 'Known Ours', 'Known Random', 'Novel Dynamem', 'Novel Ours', 'Novel Random', 'Moved Dynamem', 'Moved Ours', 'Moved Random'],
        [known_dynamem_spl, known_ours_spl, known_random_spl, novel_dynamem_spl, novel_ours_spl, novel_random_spl, moved_dynamem_spl, moved_ours_spl, moved_random_spl],
        color=['blue', 'orange', 'green', 'blue', 'orange', 'green', 'blue', 'orange', 'green']
    )
    plt.ylim(0, 1)
    plt.ylabel('SPL')
    plt.title('Simulation SPL')

    plt.show()

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Plot simulation results from a .npz file.")
    # parser.add_argument("file_path", type=Path, help="Path to the .json file containing simulation results.")
    # args = parser.parse_args()
    main()
