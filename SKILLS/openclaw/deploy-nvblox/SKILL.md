---
name: deploy-nvblox
description: Deploy Isaac ROS NVBlox with Orbbec RGB-D camera on Jetson AGX Orin for real-time GPU-accelerated 3D mapping (TSDF/ESDF). Sets up Docker CE, Isaac ROS 3.2, Orbbec SDK ROS2, and builds the NVBlox workspace for obstacle detection and 3D mesh generation. Requires JetPack 6.2 and ROS2 Humble.
---

# Deploy NVBlox with Orbbec Camera on Jetson AGX Orin

NVBlox builds dense 3D maps in real-time from RGB-D camera input for robotic navigation. This skill deploys it on AGX Orin with Isaac ROS and Orbbec camera support.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Hardware | Jetson AGX Orin (e.g. reComputer J50) |
| JetPack | 6.2 |
| Camera | Orbbec RGB-D camera (Gemini 2, 330 series, etc.) |
| ROS2 | Humble installed on host |
| NGC account | Required for Isaac ROS Docker image pull |

---

## Phase 1 — Install basic dependencies (~3 min)

```bash
sudo apt update
sudo apt-get install -y python3-pip nvidia-jetpack git-lfs
sudo pip3 install jetson-stats
```

`[OK]` when all packages install. `[STOP]` if apt fails.

---

## Phase 2 — Install Docker CE (~5 min)

```bash
sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=arm64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER
```

Reboot after adding user to docker group:

```bash
sudo reboot
```

Verify after reboot:

```bash
docker info
```

`[OK]` when `docker info` succeeds without sudo. `[STOP]` if Docker fails to start.

---

## Phase 3 — Install Isaac ROS 3.2 (~10–20 min)

```bash
mkdir -p ~/workspaces/isaac_ros-dev/src
echo "export ISAAC_ROS_WS=\${HOME}/workspaces/isaac_ros-dev/" >> ~/.bashrc
source ~/.bashrc
cd ${ISAAC_ROS_WS}/src
git clone -b release-3.2 https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common.git
```

Pull and enter the Isaac ROS Docker container:

```bash
cd ${ISAAC_ROS_WS}/src/isaac_ros_common
./scripts/run_dev.sh
```

This will pull the NGC Docker image and start the container. You will need your NGC API Key.

If you get a CDI error, fix with:

```bash
sudo nvidia-ctk cdi generate --mode=csv --output=/etc/cdi/nvidia.yaml
```

`[OK]` when you are inside the Isaac ROS Docker container. `[STOP]` if NGC auth or Docker fails.

---

## Phase 4 — Install Orbbec SDK ROS2 on host (~10 min)

Run these commands on the host (not inside Docker):

```bash
sudo apt install -y libgflags-dev nlohmann-json3-dev \
    ros-humble-image-transport ros-humble-image-transport-plugins ros-humble-compressed-image-transport \
    ros-humble-image-publisher ros-humble-camera-info-manager \
    ros-humble-diagnostic-updater ros-humble-diagnostic-msgs ros-humble-statistics-msgs ros-humble-xacro \
    ros-humble-backward-ros libdw-dev libssl-dev mesa-utils libgl1 libgoogle-glog-dev

mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/orbbec/OrbbecSDK_ROS2.git
cd OrbbecSDK_ROS2 && git checkout v2-main
cd ~/ros2_ws
colcon build --event-handlers console_direct+ --cmake-args -DCMAKE_BUILD_TYPE=Release
```

Install udev rules:

```bash
cd ~/ros2_ws/src/OrbbecSDK_ROS2/orbbec_camera/scripts
sudo bash install_udev_rules.sh
sudo udevadm control --reload-rules && sudo udevadm trigger
```

`[OK]` when colcon build completes and udev rules are installed. `[STOP]` if build fails.

---

## Phase 5 — Build NVBlox in Isaac ROS container (~15 min)

Clone the Orbbec-adapted NVBlox source:

```bash
git clone https://github.com/jjjadand/isaac-NVblox-Orbbec.git
cp -r isaac-NVblox-Orbbec/src/isaac_ros_nvblox/ ${ISAAC_ROS_WS}/src/
cp -r isaac-NVblox-Orbbec/src/isaac_ros_nitros/ ${ISAAC_ROS_WS}/src/
cp -r isaac-NVblox-Orbbec/build/ ${ISAAC_ROS_WS}/
```

Enter the Docker container and build:

```bash
cd ${ISAAC_ROS_WS}/src/isaac_ros_common && ./scripts/run_dev.sh

# Inside container:
sudo apt update
sudo apt-get install -y ros-humble-magic-enum ros-humble-foxglove-msgs

echo 'CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export CUDACXX=$CUDA_HOME/bin/nvcc' >> ~/.bashrc

sudo ln -sf /opt/ros/humble/include/magic_enum.hpp /usr/include/magic_enum.hpp
sudo mkdir -p /opt/ros/humble/include/foxglove_msgs
sudo ln -sfn /opt/ros/humble/include/foxglove_msgs/foxglove_msgs/msg /opt/ros/humble/include/foxglove_msgs/msg

colcon build --symlink-install --cmake-args -DBUILD_TESTING=OFF
source install/setup.bash
```

`[OK]` when colcon build completes with all packages. `[STOP]` if compilation errors.

---

## Phase 6 — Launch NVBlox (~2 min)

On the host, start the Orbbec camera node:

```bash
cd ~/ros2_ws
source install/setup.bash
ros2 launch orbbec_camera gemini2.launch.py
# Replace gemini2 with your camera model: gemini210, gemini2L, gemini_330_series, etc.
```

In the Isaac ROS Docker container, verify topics and launch NVBlox:

```bash
ros2 topic list
# Should show /camera/color/image_raw, /camera/depth/image_raw, etc.

cd ~/workspaces/isaac_ros-dev
source install/setup.bash
ros2 launch nvblox_examples_bringup orbbec_example.launch.py
```

`[OK]` when RViz shows 3D occupancy grids and meshes.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| NGC auth fails | Regenerate API key at https://ngc.nvidia.com. Run `ngc config set` again. |
| CDI device error on `run_dev.sh` | Run: `sudo nvidia-ctk cdi generate --mode=csv --output=/etc/cdi/nvidia.yaml`. |
| Orbbec camera not detected | Install udev rules (Phase 4). Replug camera. Check `lsusb`. |
| No camera topics in Docker | Orbbec node must run on host, not in Docker. Verify ROS_DOMAIN_ID matches. |
| colcon build fails on NVBlox | Check magic_enum and foxglove_msgs are installed. Verify CUDA env vars. |
| RViz shows no data | Confirm camera topics are publishing: `ros2 topic hz /camera/depth/image_raw`. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with Docker setup, build details, RViz configuration, and demo video (reference only)
