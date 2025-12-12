# stretch_isaac
## Quick Start Overview
This repository provides an Isaac Sim environment for deploying and testing the Hello Robot **Stretch** with ROS 2.
A minimal end-to-end workflow is as follows:
1. Install prerequisites (Pixi, Isaac Sim, ROS 2).
2. Launch Isaac Sim using Pixi.
3. Open an example scene or create a new environment.
4. Import the Stretch USD model into the scene.
5. Verify physics and joint dynamics.
6. Enable and configure the ROS 2 bridge (already enabled by default).
7. Play the simulation.
8. Run ROS 2 nodes and test base and joint control.

This README explains each step in more detail below.

## Prerequisites

- Pixi installed for Isaac Sim 5.1.0 and ROS2 Humble
  (https://pixi.sh/dev/installation/)
- NVIDIA GPU with up-to-date drivers  
- `ros2-bridge` plugin enabled in Isaac Sim 
  - It is already automatically enabled. 
  - Go to Window > Extensions, find "ROS 2 Bridge," and verify it is **Enabled**.

## Directory Layout

- `Robot_Import_Files/` – modified URDF with updated collision meshes
- `importable_stretch.usd/` - Refrence ready USD, for import into environments.
- `hm3d_scene.usd/` – Issac Sim USD stage with the imported robot
- `interior_agent_scene.usd` – Issac Sim USD stage with the imported robot
- `README.md`         – this file

## Import Process

Adapted from the Isaac Sim docs:  
- https://docs.isaacsim.omniverse.nvidia.com/4.5.0/robot_setup/import_urdf.html  
- https://docs.isaacsim.omniverse.nvidia.com/4.5.0/ros2_tutorials/index.html  

1. **Create or Open an Isaac Sim Scene**  
   You may either open an existing prepared scene or create your own.

   - `interior_agent_scene.usd`
     - Contains the InteriorAgent scene `kujale_0003` with Stretch already imported  
       Dataset: https://huggingface.co/datasets/spatialverse/InteriorAgent/tree/main

   - `hm3d_scene.usd`
     - Contains an HM3D environment with Stretch already imported  
       Dataset: https://github.com/matterport/habitat-matterport-3dresearch

   > **Note:**  
   > If you try to open either of these two scenes, make sure you have downloaded the corresponding datasets and that Isaac Sim can locate them on your local system.  
   >  
   > After opening one of these scenes, you may skip **Step 2**.

   You may also use built-in Isaac Sim assets:
   - Navigate to **Content > Isaac Sim** to browse default environments and props.

   **Physics note:**  
   For objects to interact physically with the robot:

   - Select the object in the **Stage** window  
   - Right-click → **Add > Physics > Rigid Body**  
   - Add a **Collider Preset**

2. **Import the Stretch as USD File** 
  If your scene does not already include the robot:
    - Import `importable_stretch.usd` into the current stage
    - Use **File > Import Reference** so the robot remains reusable
  Model details: 
    - Original URDF used square collision meshes on the wheels, which caused physics artifacts.  
    - Replace them with cylinders; see `Robot_Import_Files/`.  
    - Enable self-collision and set the base link movable.
  
3. **Tune joint dynamics**
  Proper joint tuning is critical for stable simulation.
  - **Wheels** 
    - Joints: `link_right_wheel` and `link_left_wheel`
    - Recommended parameters
      - Armature: 2.0 kg·m² (reduces jitter)  
      - Damping: 1000
      - Stiffness: 0  
      - Max torque and brake force clamped
    > Where to set this in the UI:
    > - Select the wheel link in the Stage window
    > - Open the Property panel
    > - Navigate to **Physics > Articulation > Drive**
  - **Positional joints (arm, lift, wrist)**  
    - Armature: 0.1 kg·m²  
    - Damping & stiffness hand-tuned via GUI  
      - **Tools > Robotics > Asset Editors > Gain Tuner**

4. **ROS 2 Bridge configuration** (synchronized to system time)  
  - Adapt or reuse OmniGraph templates from **Window > Graph Editors > Action Graph**
  - **ROS2 Topic Overview**
    | Component | Topics                           | Direction | Purpose                     |
    | :--------- | :-------------------------------- | :--------- | :--------------------------- |
    | Base      | `/stretch/cmd_vel`               | Sub       | Differential drive control  |
    | Joints    | `/joint_command`, `/joint_state` | Sub / Pub | Joint commands and feedback |
    | Camera    | `/spectacular_ai/*`              | Pub       | RGB, depth, point cloud     |
    | Lidar     | `/scan_filtered`                 | Pub       | Laser scan                  |
    | TF        | `/tf`, `/tf_static`              | Pub       | Coordinate transforms       |
    | State     | `/state_estimator/pose_filtered` | Pub       | Estimated robot pose        |
    | Homing    | `/is_homed`                      | Pub / Srv | Robot homing status         |

## Launching the Simulation
1. Enter the Pixi environment in the root diretory of this repo:
    ```bash
    pixi shell
    ```
2. Launch Isaac Sim
    ```bash
    isaacsim
    ```
3. Open a scene or import the Stretch USD.
4. Press **Play** to start the simulation.
5. Run ROS2 nodes in a separate terminal.

## Testing

1. **Base Motion Control (`/stretch/cmd_vel`)**
  - This command controls the differential drive of the robot base.
      ```bash
      ros2 topic pub --once /stretch/cmd_vel \
      geometry_msgs/msg/Twist "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.5}}"
      ```
  > Expected behavior:
  > - The robot rotates in place.
  > 
  > If the robot does not move:
  > - Check wheel joint drive settings
  > - Verify ground plane has a collider
  > - Ensure simulation is playing
2. **Joint-Level Control (`/joint_command`)**
  - This command controls individual articulated joints (arm, lift, wrist).
    ```bash
    $ ros2 topic pub /joint_command \
    sensor_msgs/JointState "{name: ['joint_lift'], position: [0.2]}"
    ```
  - Verify feedback:
    ```bash
    $ ros2 topic echo /joint_state
    ```
  > Expected behavior:
  > - The joint moves to the commanded position.
  > - `/joint_state` reflects the correct value.
  > 
  > If the joints do not move:
  > - Check the max angle or max force value of the joints.
  > - Recheck armature, damping, and stiffness values.
