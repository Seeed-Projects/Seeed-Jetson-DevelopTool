---
name: ethercat-setup
description: Establish EtherCAT communication between Jetson and EtherCAT slave devices using the EtherLab EtherCAT Master driver. Covers driver installation, configuration, slave scanning, and motor control example (MyActuator X4). Requires JetPack 6.2 (L4T 36.4.3).
---

# EtherCAT Setup on Jetson with EtherLab Master

---

## Execution model

Run one phase at a time. After each phase:
- Relay all command output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree below.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Hardware | reComputer Robotics J401 (or compatible Jetson) as EtherCAT master |
| Slave device | EtherCAT slave (e.g. MyActuator X4) with external power |
| JetPack | 6.2 (L4T 36.4.3) |
| Cable | Ethernet cable + adapter if slave uses 4-pin interface (Tx+, Tx–, Rx+, Rx–) |

> Most slave devices require additional external power after physical Ethernet connection.

---

## Phase 1 — Hardware connection (~2 min)

Connect the Jetson Ethernet interface directly to the EtherCAT slave device. If the slave uses a 4-pin interface, use an Ethernet-to-4-pin adapter.

Identify the Ethernet interface name:

```bash
ifconfig
```

Note the interface name (e.g. `eno1`). This will be used in subsequent configuration.

`[OK]` — proceed to Phase 2.

---

## Phase 2 — Install EtherCAT driver (~5–10 min)

Install build dependencies and compile the EtherLab EtherCAT master:

```bash
sudo apt update
sudo apt install build-essential cmake libtool autoconf automake
```

```bash
git clone https://gitlab.com/etherlab.org/ethercat.git
cd ethercat
./bootstrap
./configure --sysconfdir=/etc
make all modules
sudo make modules_install install
sudo depmod -a
```

Verify the kernel modules are loaded:

```bash
sudo lsmod | grep "ec_"
```

Expected: `ec_master` and `ec_generic` modules listed.

`[OK]` — proceed to Phase 3. `[STOP]` if modules not found.

---

## Phase 3 — Configure EtherCAT master (~2 min)

Edit the configuration file:

```bash
sudo vim /etc/ethercat.conf
```

Set these parameters (replace `eno1` with your interface name):

```
MASTER0_DEVICE="eno1"
DEVICE_MODULES="generic"
```

Restart the service and verify:

```bash
sudo systemctl restart ethercat
ls /dev/EtherCAT*
```

Expected: `/dev/EtherCAT0` appears.

(Optional) If `/dev/EtherCAT` is not found, try loading modules manually:

```bash
sudo modprobe ec_master devices="eno1"
sudo modprobe ec_generic
sudo systemctl restart ethercat
```

(Optional) If the interface is occupied by NetworkManager:

```bash
sudo nmcli dev set eno1 managed no
sudo nmcli dev set eno1 managed on
```

`[OK]` — proceed to Phase 4. `[STOP]` if `/dev/EtherCAT0` does not appear.

---

## Phase 4 — Test communication (~2 min)

Scan for EtherCAT devices and check packet loss:

```bash
sudo ethercat rescan
sudo ethercat master
```

List all slaves on the bus:

```bash
sudo ethercat rescan
sudo ethercat slaves -v
```

View PDOs of slave at index 0:

```bash
sudo ethercat rescan
sudo ethercat pdos -p 0
```

`[OK]` — slaves detected and communication verified. `[STOP]` if no slaves found.

---

## Phase 5 — Motor control example (MyActuator X4, optional) (~5 min)

Clone and build the example motor control code:

```bash
git clone https://github.com/jjjadand/ethercat-myctor.git
cd ethercat-myctor/src/build
cmake ..
make
```

Lock CPU frequency and run:

```bash
sudo jetson_clocks
sudo ./ethercat_master
```

Expected: after ~2 seconds, the motor begins to move in a loop.

`[OK]` — EtherCAT motor control working.

> Each EtherCAT motor uses a different communication protocol. Adapt the example for your specific device.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `./bootstrap` fails | Ensure `autoconf` and `automake` are installed. |
| `ec_master` / `ec_generic` not in `lsmod` | Re-run `sudo depmod -a` and `sudo modprobe ec_master`. Check kernel version compatibility. |
| `/dev/EtherCAT0` not found | Verify `MASTER0_DEVICE` in `/etc/ethercat.conf` matches your interface. Try manual `modprobe`. |
| Interface occupied by NetworkManager | Run `sudo nmcli dev set <iface> managed no` then restart ethercat service. |
| `ethercat slaves` shows no slaves | Check physical cable connection. Ensure slave has external power. Try different Ethernet port. |
| High packet loss in `ethercat master` | Check cable quality. Use Cat5e or better. Avoid switches between master and slave. |
| Motor example doesn't compile | Ensure EtherCAT master is installed. Check cmake can find EtherCAT headers. |

---

## Reference files

- `references/source.body.md` — full original Seeed tutorial with hardware diagrams, motor control flowchart, and CiA-402 state machine details (reference only)
