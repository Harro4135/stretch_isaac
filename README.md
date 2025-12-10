# stretch_isaac
## Prerequisites

- Pixi installed for IsaacSim and ROS2(https://pixi.sh/dev/installation/)
- NVIDIA GPU with up-to-date drivers  
- `ros2-bridge` plugin enabled in Isaac Sim  

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

1. **Create a new Isaac Sim project with importing scenes**  
  - the file `interior_agent_scene.usd` contains the scene (including imported stretch) `kujale_0003` from the dataset https://huggingface.co/datasets/spatialverse/InteriorAgent/tree/main (skip step 2)
  - the file `hm3d_scene.usd` contains a scene (including imported stretch) from the [Habitat-Matterport3D](https://github.com/matterport/habitat-matterport-3dresearch?tab=readme-ov-file) dataset (skip step 2)
  - There are existing environments and assets for setting up environments with the path Content>Isaac Sim
    - To enable physics performance, select your object (like a cube or Xform), right-click it in the Stage window, and choose Add > Physics > Rigid Body, then add a Collider Preset for interaction
2. **Import the Stretch as USD File** 
  - Import `importable_stretch.usd` into your IsaacSim stage
  - Original URDF used square collision meshes on the wheels, which caused physics artifacts.  
  - Replaced them with cylinders; see `Robot_Import_Files/`.  
  - Enabled self-collision and set the base link movable.  
3. **Tune joint dynamics**  
  - **Wheels**  
    - `link_right_wheel` and `link_left_wheel`
    - Armature: 2.0 kg·m² (reduces jitter)  
    - Damping: 1000; Stiffness: 0  
    - Clamped max torque and brake force  
  - **Positional joints**  
    - Armature: 0.1 kg·m²  
    - Damping & stiffness hand-tuned via GUI  
      (Tools > Robotics > Asset Editors > Gain Tuner)
4. **ROS 2 Bridge configuration** (synchronized to system time)  
   - Adapt or reuse OmniGraph templates from  
     Tools > Robotics > ROS 2 OmniGraphs  
   - Key graphs:  
    1. Camera broadcast 
      - `/spectacular_ai/camera_info` 
      - `/spectacular_ai/point_cloud`
      - `/spectacular_ai/depth_image`
      - `/spectacular_ai/color_image`
    2. Lidar broadcast
      - `/scan_filtered`
    3. TF/ TF static broadcast
      - `/tf`
      - `/tf_static`
    4. Estimated state publisher
      - `/state_estimator/pose_filtered`
    5. Differential controller 
      - `/stretch/cmd_vel`
    6. Joint state publisher/subscriber and controller
      - `/joint_state`
      - `/joint_command`
    7. Home The Robot publisher and service server
      - `/is_homed`

## Launching the Simulation
1. To install Isaac Sim with Pixi do
  - `pixi shell` (in the root diretory of this repo)
  - launch by executing `isaacsim`
2. Play simulation and run ROS2 nodes

## Future Work
- Force feedback gripper control
