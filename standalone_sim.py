# launch Isaac Sim before any other imports
# default first two lines in any standalone application
import argparse
import json
from pathlib import Path
from typing import Literal, Union

import numpy as np
from isaacsim import SimulationApp

app = SimulationApp({"headless": False})  # we can also run as headless.

import omni.kit.actions.core
from isaacsim.core.api import World
from isaacsim.core.utils import extensions
from omni.isaac.core.articulations import Articulation
from omni.isaac.core.utils.stage import add_reference_to_stage
from pxr import Sdf, Usd, UsdGeom, Gf, PhysxSchema


def switch_lighting(mode: Literal["camera", "stage"] = "camera"):
    # switch lighting
    action_registry = omni.kit.actions.core.get_action_registry()
    action = action_registry.get_action("omni.kit.viewport.menubar.lighting", "set_lighting_mode_" + mode)
    action.execute()


def get_visibility_attribute(stage: Usd.Stage, prim_path: str) -> Union[Usd.Attribute, None]:
    """Return the visibility attribute of a prim"""
    path = Sdf.Path(prim_path)
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        return None
    visibility_attribute = prim.GetAttribute("visibility")
    return visibility_attribute


def hide_prim(stage: Usd.Stage, prim_path: str):
    """Hide a prim

    Args:
        stage (Usd.Stage, required): The USD Stage
        prim_path (str, required): The prim path of the prim to hide
    """
    visibility_attribute = get_visibility_attribute(stage, prim_path)
    if visibility_attribute is None:
        return
    visibility_attribute.Set("invisible")


def show_prim(stage: Usd.Stage, prim_path: str):
    """Show a prim

    Args:
        stage (Usd.Stage, required): The USD Stage
        prim_path (str, required): The prim path of the prim to show
    """
    visibility_attribute = get_visibility_attribute(stage, prim_path)
    if visibility_attribute is None:
        return
    visibility_attribute.Set("inherited")


def dump_state(
    time: float,
    position: tuple[float, 3],
    orientation: tuple[float, 4],
    linear_velocity: tuple[float, 3],
):
    data = {
        "time": time,
        "position": {"x": position[0], "y": position[1], "z": position[2]},
        "orientation": {
            "w": orientation[0],
            "x": orientation[1],
            "y": orientation[2],
            "z": orientation[3],
        },
        "linear_velocity": {
            "vx": linear_velocity[0],
            "vy": linear_velocity[1],
            "vz": linear_velocity[2],
        },
    }
    print("<robot>" + json.dumps(data) + "</robot>")


def dump_prim_position(prims: list[Usd.Prim]):
    data = {}
    for prim in prims:
        xformable = UsdGeom.Xformable(prim)
        world_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        pos = world_matrix.ExtractTranslation()
        data[prim.GetName()] = {"x": round(pos[0], 2), "y": round(pos[1], 2), "z": round(pos[2], 2)}
    print("<goals>" + json.dumps(data) + "</goals>")


def parse_assets(raw_assets):
    assets = []
    for name, x, y, z, theta in raw_assets or []:
        assets.append((name, float(x), float(y), float(z), float(theta)))
    return assets


def get_toplevel_prims_substring(search_root: Usd.Prim, prim_substring: list[str], references_only: bool = False) -> list[Usd.Prim]:
    matched_prims = []
    for prim in Usd.PrimRange(search_root):
        prim_name = prim.GetName()

        has_payload = prim.HasPayload()
        has_reference = prim.HasAuthoredReferences()
        valid = (not references_only) or (has_reference or has_payload)
        if has_payload or has_reference:
            print(f"{prim_name}: payload={has_payload}, reference={has_reference}")

        if any(
            (valid and substring in prim_name and substring not in str(prim.GetPath().GetParentPath()))
            for substring in prim_substring
        ):
            matched_prims.append(prim)
    return matched_prims


def set_prim_pose(prim, pos, theta):
    xform = UsdGeom.Xformable(prim)

    # translate
    ops = xform.GetOrderedXformOps()
    t_op = next((op for op in ops if op.GetOpName() == "xformOp:translate"), None)
    if t_op is None:
        t_op = xform.AddTranslateOp()
    t_op.Set(Gf.Vec3d(*pos))

    # rotate Z
    r_op = xform.AddRotateZOp()
    r_op.Set(float(theta))


def disable_collision(root_prim: Usd.Prim):
    for prim in Usd.PrimRange(root_prim):
        collision_api = PhysxSchema.PhysxCollisionAPI.Apply(prim)
        attr = collision_api.GetPrim().GetAttribute("physics:collisionEnabled")
        if attr:
            attr.Set(False)
        # attr.Set(False)
        # if not attr:
        #     # Create it if missing
        #     attr = collision_api.GetPrim().CreateAttribute("physics:collisionEnabled", Sdf.ValueTypeNames.Bool)


def main(simulation_app):
    parser = argparse.ArgumentParser(description="Run standalone simulation with optional scene selection.")
    parser.add_argument(
        "--scene",
        type=Path,
        help="Path to the USD scene file to load.",
        default=None,
    )
    parser.add_argument(
        "--lighting",
        type=str,
        choices=["camera", "stage"],
        default="stage",
        help="Lighting mode to use.",
    )
    parser.add_argument(
        "--asset",
        nargs=5,
        action="append",
        metavar=("NAME", "X", "Y", "Z", "THETA"),
        help="Asset definition: name x y z theta (in deg) (can be provided multiple times)",
        default=[],
    )
    parser.add_argument(
        "--rasset",
        type=str,
        help="Substring of assets to remove from the scene.",
        nargs="*",
        default=[],
    )
    parser.add_argument(
        "--rasset-exclude",
        type=str,
        help="Substring of assets to exclude from removal even if they match rasset.",
        nargs="*",
        default=[],
    )
    parser.add_argument(
        "--gasset",
        type=str,
        help="Goal assets to broadcast their position.",
    )
    args = parser.parse_args()
    args.asset = parse_assets(args.asset)

    extensions.enable_extension("isaacsim.ros2.bridge")
    simulation_app.update()

    root_prim = "/map"

    goal_assets = []
    if args.scene is not None:
        print(f"Loading scene from {args.scene}")
        omni.usd.get_context().open_stage(str(args.scene))
        world = World()
        _scene = world.stage.GetPrimAtPath("/Root")
        hide_assets = get_toplevel_prims_substring(_scene, args.rasset, True)
        for prim in hide_assets:
            if any(exclude in prim.GetName() for exclude in args.rasset_exclude):
                print(f"Excluding prim {prim.GetPath()} from hiding")
                continue
            print(f"Hiding prim {prim.GetPath()}")
            hide_prim(world.stage, str(prim.GetPath()))

        print(f"Searching for goal assets with substring: {args.gasset}")
        goal_assets = get_toplevel_prims_substring(_scene, [args.gasset]) if args.gasset is not None else []

        print(f"Disabling collision for scene {_scene.GetPath()}")
        disable_collision(_scene)

    ground_plane = world.scene.add_ground_plane(prim_path=root_prim + "/defaultGroundPlane", z_position=0.05)
    if args.scene is not None:
        hide_prim(world.stage, ground_plane.prim_path)

    # print(f"Setting lighting mode to {args.lighting}")
    # switch_lighting(mode=args.lighting)

    # load robot
    stretch_asset_path = "/home/benni/repos/stretch_isaac/importable_stretch_no_arm_collider.usd"
    prim_stretch = add_reference_to_stage(usd_path=stretch_asset_path, prim_path=root_prim)

    for id, asset in enumerate(args.asset):
        asset_usd_path, x, y, z, theta = asset
        name = Path(asset_usd_path).stem
        print(
            f"Adding asset '{name}' at position ({x}, {y}, {z}) with rotation {theta} and asset path '{asset_usd_path}'"
        )
        prim_asset = add_reference_to_stage(usd_path=str(asset_usd_path), prim_path=f"{root_prim}/{name}_{id}")
        set_prim_pose(prim_asset, (x, y, z), theta)
    world.reset()

    stretch = Articulation(prim_path=str(prim_stretch.GetPath()) + "/stretch")
    stretch.initialize()

    print_pose_interval: int = 33
    print_goal_interval: int = 110
    try:
        step_count = 0
        while simulation_app.is_running():
            world.step(render=True)  # execute one physics step and one rendering step
            step_count += 1
            if step_count % print_pose_interval == 0:
                position: np.ndarray
                orientation: np.ndarray
                position, orientation = stretch.get_world_pose()
                linear_velocity: np.ndarray = stretch.get_linear_velocity()
                dump_state(
                    float(world.current_time),
                    position.tolist(),
                    orientation.tolist(),
                    linear_velocity.tolist(),
                )
            if step_count % print_goal_interval == 0:
                dump_prim_position(goal_assets)
            if step_count > 1e4:
                step_count = 0
    except KeyboardInterrupt:
        print("Exiting simulation...")

    simulation_app.close()


if __name__ == "__main__":
    main(app)
