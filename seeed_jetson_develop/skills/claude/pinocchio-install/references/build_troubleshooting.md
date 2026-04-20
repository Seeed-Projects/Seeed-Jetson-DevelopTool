# Pinocchio Source-Build Troubleshooting Playbook

Each section: **symptom → root cause → fix → verify**

---

## B1 — conda-forge no pre-built arm64 binary

**Symptom:**
```
PackagesNotFoundError: The following packages are not available from current channels: pinocchio
```
or build from source begins unexpectedly and fails.

**Root cause:**
conda-forge arm64 (aarch64) packages may not exist for the requested version.

**Fix:**
```bash
# Option A: use pip
pip install pin

# Option B: build from source
bash ~/.agents/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method source --phase deps
bash ~/.agents/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method source --phase build
```

**Verify:**
```bash
python -c "import pinocchio; print(pinocchio.__version__)"
```

---

## B2 — eigenpy not found after deps phase

**Symptom:**
```
[STOP] eigenpy not available via pip and conda is absent
```
or cmake error:
```
Could not find a configuration file for package "eigenpy"
```

**Root cause:**
eigenpy is not packaged by pip for all platforms. On arm64 it may need to be compiled.

**Fix — try pip first:**
```bash
pip install eigenpy
```

**Fix — conda-forge:**
```bash
conda install -c conda-forge eigenpy
```

**Fix — robotpkg (Ubuntu 20.04/22.04/24.04, x86-64 only):**
```bash
sudo mkdir -p /etc/apt/keyrings
curl http://robotpkg.openrobots.org/packages/debian/robotpkg.asc \
  | sudo tee /etc/apt/keyrings/robotpkg.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/robotpkg.asc] \
  http://robotpkg.openrobots.org/packages/debian/pub $(lsb_release -cs) robotpkg" \
  | sudo tee /etc/apt/sources.list.d/robotpkg.list
sudo apt-get update
sudo apt-get install robotpkg-py310-eigenpy
export PYTHONPATH=/opt/openrobots/lib/python3.10/site-packages:$PYTHONPATH
export LD_LIBRARY_PATH=/opt/openrobots/lib:$LD_LIBRARY_PATH
```

**Verify:**
```bash
python3 -c "import eigenpy; print('eigenpy OK')"
```

---

## B3 — cmake configure failed: missing dependency

**Symptom:**
```
[STOP] cmake configure failed
```
cmake output may contain:
- `Could not find a configuration file for package "urdfdom"`
- `Could not find a configuration file for package "Eigen3"`
- `Could not find a configuration file for package "Boost"`

**Root cause:**
One or more required packages are not installed or not on CMAKE_PREFIX_PATH.

**Fix — missing urdfdom:**
```bash
sudo apt install liburdfdom-dev liburdfdom-headers-dev
```

**Fix — missing Eigen3:**
```bash
sudo apt install libeigen3-dev
```

**Fix — missing Boost:**
```bash
sudo apt install libboost-all-dev
```

**Fix — prefix not on CMAKE_PREFIX_PATH (e.g. robotpkg install):**
Add to cmake command:
```bash
cmake -S ~/pinocchio_src -B ~/pinocchio_src/build \
  -DCMAKE_PREFIX_PATH=/opt/openrobots \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=$HOME/.local \
  -DBUILD_PYTHON_INTERFACE=ON \
  -DBUILD_TESTING=OFF
```

**Verify:**
```bash
cmake --build ~/pinocchio_src/build --parallel 2
```

---

## B4 — make failed: compiler error

**Symptom:**
```
[STOP] make failed
```
Build output shows C++ compilation errors.

**Common causes and fixes:**

| Error pattern | Fix |
|---------------|-----|
| `error: 'auto' not allowed in function prototype` | Compiler too old (need ≥ GCC 8). Run: `sudo apt install gcc-10 g++-10` then add `-DCMAKE_CXX_COMPILER=g++-10` |
| `fatal error: Eigen/Core: No such file` | `sudo apt install libeigen3-dev` |
| `virtual memory exhausted` or `OOM killed` | Reduce parallelism: edit script's NPROC to 1 or 2 |
| `error: boost/...` | `sudo apt install libboost-all-dev` |
| `undefined reference to eigenpy::...` | eigenpy version mismatch; reinstall eigenpy matching pinocchio's required version |

**Reduce parallelism manually:**
```bash
cmake --build ~/pinocchio_src/build --parallel 1
```

**Verify:**
```bash
cmake --install ~/pinocchio_src/build
python3 -c "import pinocchio"
```

---

## B5 — import pinocchio failed after source build

**Symptom:**
```
[STOP] import pinocchio failed
```
Python error:
```
ModuleNotFoundError: No module named 'pinocchio'
```
or:
```
ImportError: libpinocchio.so.X: cannot open shared object file
```

**Root cause:**
PYTHONPATH and/or LD_LIBRARY_PATH do not include the install prefix.

**Fix:**
```bash
# Determine python version
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PREFIX=$HOME/.local   # or whatever --prefix was set to

export PYTHONPATH=$PREFIX/lib/python${PY_VER}/site-packages:$PYTHONPATH
export LD_LIBRARY_PATH=$PREFIX/lib:$LD_LIBRARY_PATH
```

**Make permanent — add to ~/.bashrc:**
```bash
echo "export PYTHONPATH=$HOME/.local/lib/python3.10/site-packages:\$PYTHONPATH" >> ~/.bashrc
echo "export LD_LIBRARY_PATH=$HOME/.local/lib:\$LD_LIBRARY_PATH" >> ~/.bashrc
source ~/.bashrc
```

**Verify:**
```bash
python3 -c "import pinocchio; print(pinocchio.__version__)"
```

---

## B6 — pip install pin fails on aarch64

**Symptom:**
```
ERROR: Could not find a version that satisfies the requirement pin
```
or wheel download fails for aarch64.

**Root cause:**
PyPI `pin` package does not publish arm64 wheels for all versions.

**Fix:**
Use `--method source` instead:
```bash
bash ~/.agents/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method source --phase deps
bash ~/.agents/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method source --phase build
bash ~/.agents/skills/pinocchio-install/scripts/install_pinocchio.sh \
  --env <ENV> --method source --phase validate
```

---

## B7 — submodule missing (source clone incomplete)

**Symptom:**
cmake configure error referencing `cmake/base` or `jrl-cmakemodules`:
```
Could not find a package configuration file provided by "jrl-cmakemodules"
```

**Root cause:**
Git submodules were not cloned.

**Fix:**
```bash
cd ~/pinocchio_src
git submodule update --init --recursive
```

**Verify:**
```bash
ls ~/pinocchio_src/cmake/base   # should list files
cmake -S ~/pinocchio_src -B ~/pinocchio_src/build ...  # re-run configure
```
