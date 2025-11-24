from pathlib import Path
import argparse
import json

def main(file: Path):
    # Load data from .json file
    with open(file, 'r') as f:
        data = json.load(f)

    experiments_dynamem = [exp for exp in data if exp['app'] == 'dynamem']
    experiments_ours = [exp for exp in data if exp['app'] == 'perceivesemantix']

    experiments_dynamem_search_known = [exp for exp in experiments_dynamem if "asset" not in exp["experiment"]["goal"]]
    experiments_ours_search_known = [exp for exp in experiments_ours if "asset" not in exp["experiment"]["goal"]]
    success_dynamem = [exp for exp in experiments_dynamem_search_known if exp["success"]]
    success_ours = [exp for exp in experiments_ours_search_known if exp["success"]]
    success_rates_dynamem = len(success_dynamem) / len(experiments_dynamem_search_known) if experiments_dynamem_search_known else 0
    success_rates_ours = len(success_ours) / len(experiments_ours_search_known) if experiments_ours_search_known else 0

    experiments_dynamem_search_novel = [exp for exp in experiments_dynamem if "asset" in exp["experiment"]["goal"]]
    experiments_ours_search_novel = [exp for exp in experiments_ours if "asset" in exp["experiment"]["goal"]]
    success_dynamem = [exp for exp in experiments_dynamem_search_novel if exp["success"]]
    success_ours = [exp for exp in experiments_ours_search_novel if exp["success"]]
    success_rates_dynamem_novel = len(success_dynamem) / len(experiments_dynamem_search_novel) if experiments_dynamem_search_novel else 0
    success_rates_ours_novel = len(success_ours) / len(experiments_ours_search_novel) if experiments_ours_search_novel else 0


    print(f"Dynamem Success Rates {success_rates_dynamem:.2f} over {len(experiments_dynamem_search_known)} trials")
    print(f"Ours Success Rates {success_rates_ours:.2f} over {len(experiments_ours_search_known)} trials")

    print(f"Dynamem Success Rates {success_rates_dynamem_novel:.2f} over {len(experiments_dynamem_search_novel)} trials")
    print(f"Ours Success Rates {success_rates_ours_novel:.2f} over {len(experiments_ours_search_novel)} trials")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot simulation results from a .npz file.")
    parser.add_argument("file_path", type=Path, help="Path to the .json file containing simulation results.")
    args = parser.parse_args()
    main(args.file_path)
