# Pinocchio Install Notes

Source: https://github.com/stack-of-tasks/pinocchio

---

## Method comparison

| Method | Speed | Python-only | C++ headers | arm64 | Notes |
|--------|-------|-------------|-------------|-------|-------|
| conda  | Fast (~2 min) | No | Yes | Maybe* | Preferred on x86-64 |
| pip    | Fast (~1 min) | Yes | No  | Maybe* | Linux/macOS only; package name is `pin` |
| source | Slow (10-30 min) | No | Yes | Yes | Always works; required on Jetson |

*conda-forge arm64 (aarch64) packages exist but may lag behind the latest release.

---

## Method: conda

```bash
conda create -n pinocchio python=3.10 -y
conda activate pinocchio
conda install -c conda-forge pinocchio
```

**Full environment with all optional features (collision, autodiff, OpenMP, CasADi):**
```bash
conda install -c conda-forge pinocchio example-robot-data
```

**Verify:**
```python
import pinocchio
print(pinocchio.__version__)
```

---

## Method: pip

Package name on PyPI is `pin` (not `pinocchio`):

```bash
pip install pin
```

Limitations:
- Linux and macOS only (no Windows)
- Only supports `double` scalar type
- No CppAD, CasADi, or collision bindings
- arm64 wheels may be missing for newer versions; check PyPI first

**Verify:**
```python
import pinocchio
print(pinocchio.__version__)
```

---

## Method: source (cmake)

### Required system packages (apt)

```bash
sudo apt-get install -y \
  cmake build-essential git \
  libeigen3-dev \
  libboost-all-dev \
  liburdfdom-dev liburdfdom-headers-dev \
  libconsole-bridge-dev \
  python3-dev python3-pip
```

### eigenpy (Python↔Eigen binding)

```bash
pip install eigenpy
# or via conda-forge if pip fails:
conda install -c conda-forge eigenpy
```

### Clone and build

```bash
git clone --recursive https://github.com/stack-of-tasks/pinocchio.git ~/pinocchio_src
cd ~/pinocchio_src
mkdir build && cd build

cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=$HOME/.local \
  -DBUILD_PYTHON_INTERFACE=ON \
  -DBUILD_WITH_COLLISION_SUPPORT=OFF \
  -DBUILD_TESTING=OFF

make -j$(nproc)
make install
```

### Optional cmake flags

| Flag | Effect |
|------|--------|
| `-DBUILD_WITH_COLLISION_SUPPORT=ON` | Enable HPP-FCL collision detection |
| `-DBUILD_WITH_OPENMP_SUPPORT=ON` | Parallelise computations |
| `-DBUILD_WITH_CASADI_SUPPORT=ON` | CasADi auto-diff |
| `-DCMAKE_CXX_FLAGS="-march=native"` | Native CPU optimisation (do NOT use for cross-compile) |
| `-DBUILD_TESTING=OFF` | Skip tests (faster build) |
| `-DPYTHON_EXECUTABLE=$(which python3)` | Force specific Python interpreter |

### Environment variables after source install

```bash
export PYTHONPATH=$HOME/.local/lib/python3.10/site-packages:$PYTHONPATH
export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH
export PATH=$HOME/.local/bin:$PATH
```

Add these to `~/.bashrc` for persistence.

---

## URDF support

Load robot models from URDF files:

```python
import pinocchio as pin

model, collision_model, visual_model = pin.buildModelsFromUrdf(
    "path/to/robot.urdf",
    "path/to/meshes/"
)
data = model.createData()
```

Requires `liburdfdom-dev` (source) or install `example-robot-data` via conda.

---

## Quick usage example

```python
import pinocchio as pin
import numpy as np

# Build a sample model
model = pin.buildSampleModelHumanoidRandom()
data  = model.createData()

# Random configuration
q = pin.randomConfiguration(model)

# Forward kinematics
pin.forwardKinematics(model, data, q)

# Access a joint frame
frame_id = model.getFrameId("universe")
pin.updateFramePlacements(model, data)
print(data.oMf[frame_id])
```

---

## ROS integration

Pinocchio is available as a ROS package:

```bash
# ROS 2
sudo apt install ros-$ROS_DISTRO-pinocchio
```

Or via the robotpkg apt repository:
```bash
sudo apt install robotpkg-py310-pinocchio
```

After install, set:
```bash
export PATH=/opt/openrobots/bin:$PATH
export PKG_CONFIG_PATH=/opt/openrobots/lib/pkgconfig:$PKG_CONFIG_PATH
export LD_LIBRARY_PATH=/opt/openrobots/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/opt/openrobots/lib/python3.10/site-packages:$PYTHONPATH
```
