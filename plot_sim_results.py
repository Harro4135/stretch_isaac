from pathlib import Path
import argparse
import json
from typing import Optional

import matplotlib.pyplot as plt

def select_experiments(data, app_name: Optional[str] = None, name_filter: list[str] = [], exclusive_name: list[str] = [], success: Optional[bool] = None):
    if app_name:
        data = [exp for exp in data if exp['app'] == app_name]
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
        if exp["path_length"] < 1.0:
            print(f"Warning: Experiment {exp['name']} has path length {exp['path_length']}")
    return data



def main():

    # Ours
    # data = load_result_json("/home/benni/datasets/sim_results_syn/experiments_results.json")
    data = load_result_json("/home/benni/datasets/sim_results_syn_new/experiments_results.json")
    
    known_ours_experiments = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore']))
    known_ours_success_rates = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore'], success=True)) / known_ours_experiments if known_ours_experiments > 0 else 0
    known_ours_spl = sum([(max(exp["goal_shortest_distance"], 1.0) / exp["path_length"]) for exp in select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore']) if exp["success"]]) / len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['hidden', 'explore']))

    novel_ours_experiments = len(select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore']))
    novel_ours_success_rates = len(select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore'], success=True)) / novel_ours_experiments if novel_ours_experiments > 0 else 0
    novel_ours_spl = sum([(max(exp["goal_shortest_distance"], 1.0) / exp["path_length"]) for exp in select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore']) if exp["success"]]) / len(select_experiments(data, app_name='perceivesemantix', name_filter=['hidden'], exclusive_name=['explore']))

    # Dynamem
    # data = load_result_json("/home/benni/datasets/sim_results_syn_dynamem/experiments_results.json")
    known_dynamem_experiments = len(select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore']))
    known_dynamem_success_rates = len(select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore'], success=True)) / known_dynamem_experiments if known_dynamem_experiments > 0 else 0
    known_dynamem_spl = sum([(max(exp["goal_shortest_distance"], 1.0) / exp["path_length"]) for exp in select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore']) if exp["success"]]) / len(select_experiments(data, app_name='dynamem', exclusive_name=['hidden', 'explore']))

    novel_dynamem_experiments = len(select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore']))
    novel_dynamem_success_rates = len(select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore'], success=True)) / novel_dynamem_experiments if novel_dynamem_experiments > 0 else 0
    novel_dynamem_spl = sum([(max(exp["goal_shortest_distance"], 1.0) / exp["path_length"]) for exp in select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore']) if exp["success"]]) / len(select_experiments(data, app_name='dynamem', name_filter=['hidden'], exclusive_name=['explore']))

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
    known_random_spl = sum([(max(exp["goal_shortest_distance"], 1.0) / exp["path_length"]) for exp in select_experiments(data, app_name='random', exclusive_name=['hidden', 'explore']) if exp["success"]]) / len(select_experiments(data, app_name='random', exclusive_name=['hidden', 'explore']))

    novel_random_experiments = len(select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore']))
    novel_random_success_rates = len(select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore'], success=True)) / novel_random_experiments if novel_random_experiments > 0 else 0
    novel_random_spl = sum([(max(exp["goal_shortest_distance"], 1.0) / exp["path_length"]) for exp in select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore']) if exp["success"]]) / len(select_experiments(data, app_name='random', name_filter=['hidden'], exclusive_name=['explore']))

    data = load_result_json("/home/benni/datasets/sim_results_syn_moved/experiments_results.json")
    moved_ours_experiments = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore']))
    moved_ours_success_rates = len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore'], success=True)) / moved_ours_experiments if moved_ours_experiments > 0 else 0
    moved_our_spl = sum([(exp["experiment"]["goal"]["shortest_path"] / exp["path_length"]) for exp in select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore']) if exp["success"]]) / len(select_experiments(data, app_name='perceivesemantix', exclusive_name=['explore']))

    moved_dynamem_experiments = len(select_experiments(data, app_name='dynamem', exclusive_name=['explore']))
    moved_dynamem_success_rates = len(select_experiments(data, app_name='dynamem', exclusive_name=['explore'], success=True)) / moved_dynamem_experiments if moved_dynamem_experiments > 0 else 0
    moved_dynamem_spl = sum([(exp["experiment"]["goal"]["shortest_path"] / exp["path_length"]) for exp in select_experiments(data, app_name='dynamem', exclusive_name=['explore']) if exp["success"]]) / len(select_experiments(data, app_name='dynamem', exclusive_name=['explore']))


    print("=== Known ===")
    print(f"Dynamem Success Rates {known_dynamem_success_rates:.2f} over {known_dynamem_experiments} trials")
    print(f"Ours Success Rates {known_ours_success_rates:.2f} over {known_ours_experiments} trials")
    print(f"Dynamem SPL {known_dynamem_spl:.2f}")
    print(f"Ours SPL {known_ours_spl:.2f}")

    print("=== Novel ===")
    print(f"Dynamem Success Rates {novel_dynamem_success_rates:.2f} over {novel_dynamem_experiments} trials")
    print(f"Ours Success Rates {novel_ours_success_rates:.2f} over {novel_ours_experiments} trials")
    print(f"Dynamem SPL {novel_dynamem_spl:.2f}")
    print(f"Ours SPL {novel_ours_spl:.2f}")

    print("=== Moved ===")
    print(f"Dynamem Success Rates {moved_dynamem_success_rates:.2f} over {moved_dynamem_experiments} trials")
    print(f"Ours Success Rates {moved_ours_success_rates:.2f} over {moved_ours_experiments} trials")
    print(f"Dynamem SPL {moved_dynamem_spl:.2f}")
    print(f"Ours SPL {moved_our_spl:.2f}")

    plt.bar(
        ['Known Dynamem', 'Known Ours', 'Known Random', 'Novel Dynamem', 'Novel Ours', 'Novel Random', 'Moved Dynamem', 'Moved Ours'],
        [known_dynamem_success_rates, known_ours_success_rates, known_random_success_rates, novel_dynamem_success_rates, novel_ours_success_rates, novel_random_success_rates, moved_dynamem_success_rates, moved_ours_success_rates],
        color=['blue', 'orange', 'green', 'blue', 'orange', 'green', 'blue', 'orange']
    )
    plt.ylim(0, 1)
    plt.ylabel('Success Rate')
    plt.title('Simulation Success Rates')


    # second plot for spl
    plt.figure()
    plt.bar(
        ['Known Dynamem', 'Known Ours', 'Known Random', 'Novel Dynamem', 'Novel Ours', 'Novel Random', 'Moved Dynamem', 'Moved Ours'],
        [known_dynamem_spl, known_ours_spl, known_random_spl, novel_dynamem_spl, novel_ours_spl, novel_random_spl, moved_dynamem_spl, moved_our_spl],
        color=['blue', 'orange', 'green', 'blue', 'orange', 'green', 'blue', 'orange']
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
