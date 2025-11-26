import argparse
import json
import os
from pathlib import Path
import pty
import signal
import subprocess
import sys
import threading
import time
from enum import Enum
from typing import Any, Literal, Optional, Union
import asyncio

import numpy as np
import pexpect


class OutMode(Enum):
    CONSOLE = 0
    DISABLED = 1
    ERRORS_ONLY = 2


COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "reset": "\033[0m",
}

STATE_LOCK = threading.Lock()
STATE_LIST: list = []

SUCCESS_FEEDBACK_DEFAULT: str = ""
SUCCESS_FEEDBACK_LOCK = threading.Lock()
SUCCESS_FEEDBACK: str = SUCCESS_FEEDBACK_DEFAULT

GOAL_POSITIONS_LOCK = threading.Lock()
GOAL_POSITIONS: Optional[np.ndarray] = None


def parse_sim_state(text: str):
    """Try to deserialize JSON from text; return state tuple or None if invalid."""
    if text.startswith("robot:"):
        text = text[len("robot:") :]
        try:
            data = json.loads(text)
            time = data["time"]
            position = [data["position"]["x"], data["position"]["y"], data["position"]["z"]]
            orientation = [
                data["orientation"]["w"],
                data["orientation"]["x"],
                data["orientation"]["y"],
                data["orientation"]["z"],
            ]
            linear_velocity = [
                data["linear_velocity"]["vx"],
                data["linear_velocity"]["vy"],
                data["linear_velocity"]["vz"],
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        else:
            global STATE_LOCK, STATE_LIST
            with STATE_LOCK:
                STATE_LIST.append((time, position, orientation, linear_velocity))
    elif text.startswith("goals:"):
        text = text[len("goals:") :]
        try:
            data = json.loads(text)
            positions = []
            for key in data.keys():
                pos = data[key]
                positions.append([pos["x"], pos["y"], pos["z"]])
            positions_array = np.array(positions)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print("Failed to parse goal positions from sim output:", e)
        else:
            if np.size(positions_array) == 0:
                return
            global GOAL_POSITIONS_LOCK, GOAL_POSITIONS
            with GOAL_POSITIONS_LOCK:
                GOAL_POSITIONS = positions_array


def print_line(line: str, prefix: str = ""):
    sys.stdout.write(f"{prefix}{line.strip()}\n")


def print_error_line(line: str, prefix: str = ""):
    if "error" in line.lower() or "exception" in line.lower():
        sys.stdout.write(f"{prefix}{line.strip()}\n")


def success_monitor(success_distance_threshold: float):
    global SUCCESS_FEEDBACK_LOCK, SUCCESS_FEEDBACK, GOAL_POSITIONS_LOCK, GOAL_POSITIONS, STATE_LOCK, STATE_LIST
    success_reported = False
    with SUCCESS_FEEDBACK_LOCK:
        if "SUCCESS" in SUCCESS_FEEDBACK:
            success_reported = True

    goal_positions = None
    with GOAL_POSITIONS_LOCK:
        if GOAL_POSITIONS is not None:
            goal_positions = np.array(GOAL_POSITIONS[:, :2])  # x, y

    last_state = None
    with STATE_LOCK:
        if STATE_LIST:
            last_state = STATE_LIST[-1]

    distance = float("inf")
    if goal_positions is not None and last_state is not None:
        position = np.array(last_state[1][:2])  # x, y
        distances = np.linalg.norm(goal_positions - position, axis=1)
        distance = float(np.min(distances))

    return success_reported and distance < success_distance_threshold


class ProcessHandler:
    def __init__(
        self,
        proc,
        master_fd: int,
        name: str,
        color: str,
        triggers: dict[Union[str, float], str],
        mode=OutMode.CONSOLE,
        line_handlers: list = [],
    ):
        self.proc = proc
        # master_fd is the integer file descriptor for the PTY master
        self.master_fd = master_fd
        self.name = name
        self.color = color
        self.triggers = triggers
        self.mode = mode

        self.start = time.time()
        self.fired_triggers = dict()

        self.prefix = f"{self.color}[{self.name}]{COLORS['reset']} "
        self.line_handler = line_handlers
        if self.mode == OutMode.CONSOLE:
            self.line_handler.append(lambda line: print_line(line, self.prefix))
        elif self.mode == OutMode.ERRORS_ONLY:
            self.line_handler.append(lambda line: print_error_line(line, self.prefix))

    async def forward_output_and_handle_input(self):
        try:
            while True:
                index = await self.expect([pexpect.EOF, "Enter desired mode"], async_=True)

        except pexpect.EOF:
            pass

        # Read raw bytes from the PTY master fd so prompts without newlines are shown
        accum = ""
        try:
            while True:
                try:
                    data = os.read(self.master_fd, 1024)
                except OSError:
                    break
                if not data:
                    break
                try:
                    text = data.decode("utf-8", errors="ignore")
                except Exception:
                    text = ""

                # Print text to stdout, adding prefix at line starts
                parts = text.splitlines(keepends=False)
                for line in parts:
                    if not line:
                        continue
                    for handler in self.line_handler:
                        handler(line)
                sys.stdout.flush()

                # Check string triggers against the accumulated text
                accum += text
                now = time.time() - self.start
                for pattern, response in self.triggers.items():
                    if isinstance(pattern, str) and pattern in accum and not self._recently_fired(pattern, now):
                        self.fired_triggers[pattern] = now
                        global SUCCESS_FEEDBACK_LOCK, SUCCESS_FEEDBACK
                        if "SUCCESS" in response:
                            if SUCCESS_FEEDBACK == "FAILURE":
                                if self.mode == OutMode.CONSOLE:
                                    sys.stdout.write(
                                        f"{self.prefix}SUCCESS condition detected but detected FAILURE earlier!\n"
                                    )
                                    sys.stdout.flush()
                            else:
                                with SUCCESS_FEEDBACK_LOCK:
                                    SUCCESS_FEEDBACK = "SUCCESS"
                                if self.mode == OutMode.CONSOLE:
                                    sys.stdout.write(f"{self.prefix}SUCCESS condition detected!\n")
                                    sys.stdout.flush()
                        elif "FAILURE" in response:
                            with SUCCESS_FEEDBACK_LOCK:
                                SUCCESS_FEEDBACK = "FAILURE"
                            if self.mode == OutMode.CONSOLE:
                                sys.stdout.write(f"{self.prefix}FAILURE condition detected!\n")
                                sys.stdout.flush()
                        else:
                            self._write_to_input(response)
                            if self.mode == OutMode.CONSOLE:
                                sys.stdout.write(f"{self.prefix}Fired string trigger '{pattern}': {response.strip()}\n")
                                sys.stdout.flush()

                accum = accum.splitlines(keepends=False)[-1]
        finally:
            try:
                os.close(self.master_fd)
            except Exception:
                pass

    def _recently_fired(self, pattern: Union[str, float], now: float, cooldown: float = 2.0) -> bool:
        """Check if a trigger was fired within the cooldown period."""
        if pattern not in self.fired_triggers:
            return False
        last_fired = self.fired_triggers[pattern]
        return now - last_fired < cooldown

    def _write_to_input(self, response: str):
        try:
            os.write(self.master_fd, response.encode())
        except Exception:
            pass

    def handle_time_triggers(self):
        if self.proc.poll() is not None:
            return  # process has exited
        now = time.time() - self.start
        for pattern, response in self.triggers.items():
            if (
                isinstance(pattern, (int, float))
                and pattern <= now
                and not self._recently_fired(pattern, now, cooldown=float("inf"))
            ):
                if self.mode == OutMode.CONSOLE:
                    sys.stdout.write(f"{self.prefix}Fired time trigger at {now:.1f}s: {response.strip()}\n")
                self.fired_triggers[pattern] = now
                self._write_to_input(response)


async def handle_process(p: dict):
    cmd = " ".join(p["cmd"])
    child = pexpect.spawn(cmd, cwd=p.get("cwd"), encoding="utf-8", timeout=None)
    console = p["output"] == OutMode.CONSOLE
    prefix = f"{p['color']}[{p['name']}]{COLORS['reset']} "

    print(f"Started process '{cmd}' with PID {child.pid}")
    if console:
        print(f"{prefix}Logging output to console.")
        child.logfile = sys.stdout

    async def send_after_delay(delay, text):
        await asyncio.sleep(delay)
        print(f"\nSending '{text}' to '{cmd}' after {delay} seconds")
        child.sendline(text)

    for trigger, response in p["triggers"].items():
        if isinstance(trigger, float):
            asyncio.create_task(send_after_delay(trigger, response))

    nontime_triggers = {k: v for k, v in p["triggers"].items() if isinstance(k, str)}

    # if p["output"] == OutMode.ERRORS_ONLY:
    #     nontime_triggers["error"] = ""

    try:
        while True:
            # Wait for either EOF or the prompt "do you want"
            index = await child.expect([pexpect.EOF] + list(nontime_triggers.keys()), async_=True)

            if index == 0:  # EOF
                print(f"\nCommand '{cmd}' finished!")
                break
            elif index >= 1:  # Pattern matched
                pattern = list(nontime_triggers.keys())[index - 1]
                response = nontime_triggers[pattern]
                global SUCCESS_FEEDBACK_LOCK, SUCCESS_FEEDBACK
                if "SUCCESS" in response:
                    if SUCCESS_FEEDBACK == "FAILURE":
                        if console:
                            print(f"{prefix}SUCCESS condition detected but detected FAILURE earlier!\n")
                    else:
                        with SUCCESS_FEEDBACK_LOCK:
                            SUCCESS_FEEDBACK = "SUCCESS"
                        if console:
                            print(f"{prefix}SUCCESS condition detected!\n")
                elif "FAILURE" in response:
                    with SUCCESS_FEEDBACK_LOCK:
                        SUCCESS_FEEDBACK = "FAILURE"
                    if console:
                        print(f"{prefix}FAILURE condition detected!\n")
                else:
                    child.sendline(response)
                    if console:
                        print(f"{prefix}Fired string trigger '{pattern}': {response.strip()}\n")

            else:
                print(f"Unexpected index {index} from expect.")
    except asyncio.CancelledError:
        print(f"\nTask for '{cmd}' cancelled, terminating child process...")
        try:
            child.terminate(force=True)  # force=True ensures the process is killed
            await child.expect(pexpect.EOF, async_=True)  # wait for it to exit
        except Exception as e:
            print(f"Error terminating '{cmd}': {e}")
        raise  # re-raise to let asyncio know the task was cancelled
    except pexpect.EOF:
        pass


def launch_processes(
    processes: dict[str, Any],
) -> list[asyncio.Task]:
    names = [p.get("name") for p in processes]
    # if "DynaMem" in names:
    #     subprocess.run(["rm", "-r", "/home/benni/repos/stretch_ai/.pixi"], check=False)
    #     print("Removed .pixi directory before launching DynaMem.")

    for p in processes:
        cwd = p.get("cwd")
        if not cwd:
            continue
        if not os.path.isdir(cwd):
            sys.stderr.write(f"Error: cwd for process '{p.get('name', '<unknown>')}' does not exist: {cwd}\n")
            sys.exit(1)

    tasks = []
    for p in processes:
        # # Launch thread to read output from the master fd
        # handler = ProcessHandler(
        #     proc,
        #     master_fd,
        #     p["name"],
        #     p["color"],
        #     p["triggers"],
        #     p["output"],
        #     line_handlers=p.get("line_handlers", []),
        # )
        # t = threading.Thread(target=handler.forward_output_and_handle_input)
        # t.daemon = True
        # t.start()

        # process_handlers.append(handler)
        # running_processes.append(proc)
        tasks.append(handle_process(p))
    return tasks


def terminate_processes(procs, timeout=2):
    """
    Terminate a list of subprocesses reliably.
    - First sends SIGTERM.
    - Waits up to `timeout` seconds.
    - Sends SIGKILL to any remaining processes.
    """
    pids = [proc.pid for proc in procs]
    gpids = []
    for pid in pids:
        try:
            gpid = os.getpgid(pid)
            gpids.append(gpid)
        except ProcessLookupError:
            pass
    all_pids = pids + gpids

    for id in all_pids:
        try:
            os.killpg(id, signal.SIGTERM)
        except ProcessLookupError:
            pass

    # Wait for processes to exit gracefully
    print("Waiting for processes to terminate...")
    end_time = time.time() + timeout
    for proc in procs:
        while proc.poll() is None and time.time() < end_time:
            time.sleep(0.05)

    print("Sending SIGTERM again to ensure termination...")
    for id in all_pids:
        try:
            os.killpg(id, signal.SIGTERM)
        except ProcessLookupError:
            pass

    # Wait for processes to exit gracefully
    print("Waiting for processes to terminate...")
    end_time = time.time() + timeout
    for proc in procs:
        while proc.poll() is None and time.time() < end_time:
            time.sleep(0.05)

    # Force kill any remaining processes
    print(f"Force killing remaining processes... (overall pids {pids}, and gpids {gpids})")
    for id in all_pids:
        try:
            os.killpg(id, signal.SIGKILL)
        except ProcessLookupError as e:
            print(f"Process already exited: {e}")


def latest_pkl(folder: Path) -> Optional[Path]:
    files = [f for f in folder.glob("*.pkl")]
    return max(files, key=lambda f: int(f.stem.split("-")[0])) if files else None


def check_existing_record(record: str, output_file: Path) -> bool:
    try:
        with open(output_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return False

    return any(d.get("name") == record for d in data)


def store_results(
    record: str,
    app: str,
    output_file: Path,
    experiment: dict,
    output_root: Path,
    state_trajectory: list,
    success: bool,
    time_to_complete: float,
    log_files: list[Path],
):
    state_file = output_root / f"{record}_state_trajectory.npy"
    log_files += [state_file]

    try:
        with open(output_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    # Convert list of tuples to a 2D NumPy array
    arr = np.array(
        [[time] + pos + ori + vel for time, pos, ori, vel in state_trajectory],
        dtype=float,
    )
    path_length = np.linalg.norm(np.diff(arr[:, 1:3], axis=0), axis=1).sum()

    new_record = {
        "name": record,
        "app": app,
        "experiment": experiment,
        "state_trajectory_file": state_file.resolve().absolute().as_posix(),
        "time_to_complete": time_to_complete,
        "path_length": path_length,
        "success": success,
        "log_files": [str(log_file) for log_file in log_files],
    }

    if not any(d.get("name") == new_record.get("name") for d in data):
        data.append(new_record)
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        np.save(state_file, arr)
    else:
        print(f"Experiment record '{record}' already exists in results file.")


def build_proccesses(
    app: Literal["dynamem", "perceivesemantix"], experiment: dict, output_root: Path
) -> tuple[list[dict[str, Any]], list[Path]]:
    if app.lower() not in ["dynamem", "perceivesemantix"]:
        raise ValueError(f"Unsupported app: {app}")

    issac_sim_options = []
    if "asset" in experiment["goal"]:
        asset = experiment["goal"]["asset"]
        if "position" in experiment["goal"]:
            position = experiment["goal"]["position"]
            theta = experiment["goal"].get("theta", 0.0)
            issac_sim_options += [
                "--asset",
                str(asset),
                str(position[0]),
                str(position[1]),
                str(position[2]),
                str(theta),
            ]
        else:
            issac_sim_options += [
                "--gasset",
                str(asset),
            ]
    if "remove_assets" in experiment:
        for rasset in experiment["remove_assets"]:
            issac_sim_options += [
                "--rasset",
                str(rasset),
            ]
    processes = [
        {
            "name": "IsaacSim",
            "cmd": [
                "pixi",
                "run",
                "python",
                "standalone_sim.py",
                "--scene",
                str(experiment.get("scene")),
                "--lighting",
                experiment.get("lighting", "stage"),
                *issac_sim_options,
            ],
            "cwd": "/home/benni/repos/stretch_isaac/",
            "color": COLORS["red"],
            "triggers": {},
            "output": OutMode.DISABLED,
            "line_handlers": [parse_sim_state],
        },
    ]

    output_dir = output_root / app.lower() / Path(experiment.get("scene")).stem / experiment["name"]
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    do_explore = experiment["goal"]["task"] == "explore"
    if "initialmap_experiment" in experiment:
        input_path = (
            output_root / app.lower() / Path(experiment.get("scene")).stem / experiment["initialmap_experiment"]
        )
        if app.lower() == "dynamem":
            input_path = input_path.with_suffix(".pkl")
        elif app.lower() == "perceivesemantix":
            input_path = input_path / "output"
            input_file = latest_pkl(input_path)
            if input_file is None:
                raise FileNotFoundError(f"No exploration pkl files found in {input_path}")
            input_path = input_file
        input_path = input_path.resolve()
    else:
        input_path = None

    output_files = []
    if app.lower() == "dynamem":
        if do_explore:
            dynamem_log = Path("/home/benni/repos/stretch_ai/dynamem_log")
            rel_out_dir = Path(os.path.relpath(output_dir, dynamem_log))
            options = [
                "--output-path",
                str(rel_out_dir),
                "--explore-iter",
                "10",
            ]
            # in exploration mode the map is not saved, so instead we search for an object (volcano) which is never present
            triggers = {
                "Enter desired mode [E (explore and mapping) / M (Open vocabulary pick and place)]": "M\n",
                "Enter the target object:": "volcano\n",
                "Enter the target receptacle:": "volcano\n",
                "Do you want to run navigation? [Y/n]:": "Y\n",
                "Do you want to run picking? [Y/n]:": "n\n",
                "Do you want to run placement? [Y/n]:": "n\n",
            }
            output_files += [str(output_dir), str(output_dir.with_suffix(".pkl"))]
        else:
            triggers = {
                "Enter desired mode [E (explore and mapping) / M (Open vocabulary pick and place)]": "M\n",
                "Enter the target object:": f"{experiment['goal']['label']}\n",
                "Enter the target receptacle:": "table\n",
                "Do you want to run navigation? [Y/n]:": "Y\n",
                "Do you want to run picking? [Y/n]:": "SUCCESS\n",
                "Do you want to run placement? [Y/n]:": "n\n",
            }
        if input_path is not None:
            options = [
                "--input-path",
                str(input_path),
            ]
        processes += [
            {
                "name": "Ros2BridgeServer",
                "cmd": ["sh ../scripts/run_stretch_ai_ros2_bridge_server.sh"],
                "cwd": "/home/benni/repos/stretch_ai/docker",
                "color": COLORS["yellow"],
                "triggers": {},
                "output": OutMode.DISABLED,
            },
            {
                "name": "DynaMem",
                "cmd": [
                    "pixi",
                    "run",
                    "python",
                    "-m",
                    "stretch.app.run_dynamem",
                    "--robot_ip",
                    "127.0.0.1",
                    *options,
                ],
                "cwd": "/home/benni/repos/stretch_ai",
                "color": COLORS["green"],
                "triggers": triggers,
                "output": OutMode.CONSOLE,
            },
        ]
    elif app.lower() == "perceivesemantix":
        initial_scene_path = str(input_path) if input_path is not None else '""'
        triggers = {15.0: "explore\n"} if do_explore else {15.0: f"{experiment['goal']['label']}\n"}
        triggers[" found at "] = "SUCCESS\n"
        output_files += [str(output_dir)]
        processes += [
            {
                "name": "PerceiveSemantix",
                "cmd": [
                    "pixi",
                    "run",
                    "ros2",
                    "run",
                    "perceive_semantix_ros2",
                    "perceive_semantix_node",
                    "--ros-args",
                    "-p",
                    "camera_depth_scale_to_m:=1.0",
                    "-p",
                    "image_rotations_clockwise:=1",
                    "-p",
                    "occupancy_map/floor_height:=0.1",
                    "-p",
                    f"store_output:={str(do_explore)}",
                    "-p",
                    "publishing_rate_background_pointcloud:=0.0",
                    "-p",
                    "objects/point_cloud/publishing_rate:=0.0",
                    "-p",
                    "occupancy_map/publishing_rate:=0.5",
                    "-p",
                    f"initial_scene_path:={initial_scene_path}",
                    "-p",
                    f"output_path:={str(output_dir)}",
                ],
                "cwd": "/home/benni/repos/bringup_active_mapmaintenance/perceive_semantix/",
                "color": COLORS["blue"],
                "triggers": {},
                "output": OutMode.DISABLED,
            },
            {
                "name": "StretchMPC",
                "cmd": [
                    "pixi",
                    "run",
                    "ros2",
                    "launch",
                    "stretch_mpc_ros",
                    "planner.launch.py",
                ],
                "cwd": "/home/benni/repos/bringup_active_mapmaintenance/stretch_mpc/",
                "color": COLORS["yellow"],
                "triggers": {},
                "output": OutMode.DISABLED,
            },
            {
                "name": "MainCoordinator",
                "cmd": [
                    "pixi",
                    "run",
                    "ros2",
                    "run",
                    "offline_bringup_active_mapmaintenance",
                    "main_coordinator",
                ],
                "cwd": "/home/benni/repos/bringup_active_mapmaintenance/offline_bringup_active_mapmaintenance/",
                "color": COLORS["green"],
                "triggers": triggers,
                "output": OutMode.CONSOLE,
            },
            # {
            #     "name": "NavigationGoalActionClient",
            #     "cmd": [
            #         "pixi",
            #         "run",
            #         "ros2",
            #         "run",
            #         "stretch_mpc_ros",
            #         "navigation_goal_action_client",
            #     ],
            #     "cwd": "/home/benni/repos/bringup_active_mapmaintenance/stretch_mpc/",
            #     "color": COLORS["green"],
            #     "triggers": {},
            #     "output": OutMode.DISABLED,
            # },
        ]
    return processes, output_files


def robot_has_moved(translation_threshold: float = 0.01, orientation_threshold: float = 1) -> bool:
    global STATE_LOCK, STATE_LIST
    with STATE_LOCK:
        if len(STATE_LIST) < 2:
            return False
        previous_state = STATE_LIST[-2]
        previous_position = np.array(previous_state[1][:2])  # x, y
        previous_orientation = np.array(previous_state[2])  # w, x, y, z
        previous_orientation /= np.linalg.norm(previous_orientation)

        state_now = STATE_LIST[-1]
        position_now = np.array(state_now[1][:2])  # x, y
        orientation_now = np.array(state_now[2])  # w, x, y, z
        orientation_now /= np.linalg.norm(orientation_now)

    position_change = np.linalg.norm(position_now - previous_position)
    angular_change = 2 * np.arccos(np.clip(np.abs(np.dot(previous_orientation, orientation_now)), -1.0, 1.0))
    return position_change > translation_threshold or angular_change > np.deg2rad(orientation_threshold)

async def stop_all_tasks():
    # Cancel all tasks except the one calling this function
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    print(f"Cancelling {len(tasks)} tasks...")
    for t in tasks:
        t.cancel()
    # Wait for them to finish/cancel
    await asyncio.gather(*tasks, return_exceptions=True)
    print("All tasks stopped.")

async def total_timeout_watcher(total_timeout: float):
    await asyncio.sleep(total_timeout)
    print(f"\nTotal timeout of {total_timeout} seconds reached, stopping all tasks...")
    await stop_all_tasks()

async def monitor_task(total_timeout: Optional[float], active_timeout: Optional[float], do_explore: bool):
    total_timeout_start: float = time.time()
    initial_movement_detected = False
    active_timeout_start: Optional[float] = None
    try:
        while True:
            time.sleep(0.1)

            # If max runtime was provided, start watcher thread
            if total_timeout is not None:
                elapsed = time.time() - total_timeout_start
                if elapsed >= total_timeout:
                    print(f"Total runtime of {total_timeout}s exceeded. Terminating processes.\n")
                    break

            if active_timeout is not None:
                if not initial_movement_detected and robot_has_moved():
                    initial_movement_detected = True
                    active_timeout_start = time.time()
                    print("Detected robot movement. Starting timeout timer.\n")
                if active_timeout_start is not None:
                    elapsed = time.time() - active_timeout_start
                    if elapsed >= active_timeout:
                        print(f"Max runtime of {active_timeout}s exceeded. Terminating processes.\n")
                        break

            if not do_explore and success_monitor(2.0):
                success = True
                print("Success condition met. Terminating processes.\n")
    except asyncio.CancelledError:
        print("Task for 'monitor_task' cancelled...")
    except pexpect.EOF:
        pass
    
async def run_tasks(processes, experiment):
    process_tasks = launch_processes(processes)
    main_tasks = asyncio.gather(*process_tasks)

    await main_tasks

    # active_timeout: Optional[float] = experiment.get("max_runtime", None)
    # total_timeout: Optional[float] = (active_timeout + 120.0) if active_timeout is not None else None
    
    # if total_timeout is not None:
    #     timeout_task = asyncio.create_task(total_timeout_watcher(total_timeout))
    #     main_tasks = asyncio.gather(main_tasks, timeout_task)
    
    # monitor = asyncio.create_task(monitor_task(total_timeout, active_timeout, experiment["goal"]["task"] == "explore"))
    # main_tasks = asyncio.gather(main_tasks, monitor)

    # await main_tasks

def run_expriment(app: Literal["dynamem", "perceivesemantix"], experiment: dict, output_root: Path):
    global STATE_LOCK, STATE_LIST, GOAL_POSITIONS_LOCK, GOAL_POSITIONS, SUCCESS_FEEDBACK_LOCK, SUCCESS_FEEDBACK
    processes, log_files = build_proccesses(app, experiment, output_root)

    record_key = f"{experiment['name']}_{app.lower()}"
    output_file = output_root / "experiments_results.json"
    if check_existing_record(record_key, output_file):
        print(f"Experiment record '{record_key}' already exists. Skipping experiment.")
        return

    asyncio.run(run_tasks(processes, experiment))

    # Reset globals
    with STATE_LOCK:
        state_trajectory = STATE_LIST.copy()
        STATE_LIST.clear()
    with SUCCESS_FEEDBACK_LOCK:
        SUCCESS_FEEDBACK = SUCCESS_FEEDBACK_DEFAULT
    with GOAL_POSITIONS_LOCK:
        GOAL_POSITIONS = None

    # Store results
    # store_results(
    #     record_key, app, output_file, experiment, output_root, state_trajectory, success, time_to_complete, log_files
    # )


def main():
    parser = argparse.ArgumentParser(description="Launch multiple helper processes and stop after an optional timeout.")
    parser.add_argument(
        "--experiment-json",
        type=Path,
        help="Path to experiment JSON file.",
        action="append",
    )
    parser.add_argument(
        "--app",
        type=str,
        choices=["dynamem", "perceivesemantix"],
        nargs="+",
        help="One or more apps to run (e.g. --app dynamem perceivesemantix)",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        help="Root output folder for experiment results.",
        default=Path("/home/benni/datasets/sim_results"),
    )
    args = parser.parse_args()

    for expirment_config in args.experiment_json:
        experiments: dict = json.loads(expirment_config.read_text())
        for experiment in experiments["experiments"]:
            for app in args.app:
                run_expriment(app, experiment, args.out_root)


if __name__ == "__main__":
    main()
