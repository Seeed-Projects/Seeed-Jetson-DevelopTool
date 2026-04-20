---
name: vnc-setup
description: Install and configure VNC (Vino) remote desktop on reComputer Nvidia Jetson devices. Covers server setup, password configuration, schema editing, and auto-start on login. Requires an HDMI dummy plug for headless operation.
---

# VNC Remote Desktop Setup on reComputer Jetson

Set up VNC remote desktop access on any Seeed Nvidia Jetson device using the Vino VNC server, enabling headless graphical control from Windows, macOS, or Linux clients.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop immediately, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed to the next phase.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Jetson device | Any Seeed Studio Nvidia Jetson (reComputer series) |
| JetPack | With GNOME desktop environment |
| HDMI dummy plug | Required for headless operation (no monitor) |
| Network | Jetson and client PC on the same network |

---

## Phase 1 — Install and configure VNC server (~5 min)

Install Vino:

```bash
sudo apt update
sudo apt install vino
```

Enable VNC server to start with graphical session:

```bash
cd /usr/lib/systemd/user/graphical-session.target.wants
sudo ln -s ../vino-server.service ./.
```

Configure VNC settings:

```bash
gsettings set org.gnome.Vino prompt-enabled false
gsettings set org.gnome.Vino require-encryption false
```

Set VNC password (replace `thepassword` with your desired password):

```bash
gsettings set org.gnome.Vino authentication-methods "['vnc']"
gsettings set org.gnome.Vino vnc-password $(echo -n 'thepassword'|base64)
```

`[OK]` when all gsettings commands complete without error. `[STOP]` if `vino` package fails to install.

---

## Phase 2 — Edit Vino schema and compile (~3 min)

Back up and edit the Vino schema to add the `enabled` key:

```bash
cd /usr/share/glib-2.0/schemas
sudo cp org.gnome.Vino.gschema.xml org.gnome.Vino.gschema.xml.old
```

Add the following XML block inside the `<schema>` element of `org.gnome.Vino.gschema.xml`, before the closing `</schema>` tag:

```xml
<key name='enabled' type='b'>
      <summary>Enable remote access to the desktop</summary>
      <description>
              If true, allows remote access to the desktop via the RFB
              protocol. Users on remote machines may then connect to the
              desktop using a VNC viewer.
      </description>
      <default>false</default>
    </key>
```

Compile schemas and reboot:

```bash
sudo glib-compile-schemas /usr/share/glib-2.0/schemas
sudo reboot
```

`[OK]` when schema compiles without error and system reboots. `[STOP]` if `glib-compile-schemas` reports XML errors.

---

## Phase 3 — Start VNC server and connect (~2 min)

After reboot, start the VNC server:

```bash
/usr/lib/vino/vino-server
```

Get the Jetson IP address:

```bash
ifconfig
```

Note the IP from `eth0` (ethernet), `wlan0` (WiFi), or `l4tbr0` (USB device mode).

Connect from a client:
- Windows: Install [VNC Viewer](https://www.realvnc.com/en/connect/download/viewer/), enter the Jetson IP
- macOS: Use Screen Sharing app at `/System/Library/CoreServices/Applications`
- Linux: `sudo apt install gvncviewer && gvncviewer <jetson-ip>`

`[OK]` when you can see the Jetson desktop remotely. `[STOP]` if connection is refused.

---

## Phase 4 — (Optional) Enable VNC auto-start on login

Open "Startup Application Preferences" on the Jetson, click Add, and set the Command field to:

```bash
nohup /usr/lib/vino/vino-server > /dev/null 2>&1 &
```

Restart the Jetson, disconnect the monitor, and connect the HDMI dummy plug. Verify VNC access works.

`[OK]` when VNC connects after reboot without a monitor attached.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `apt install vino` fails | Check internet. Run `sudo apt update` first. |
| gsettings errors — no schema | Ensure GNOME desktop is installed. Vino requires a graphical session. |
| `glib-compile-schemas` XML error | Restore backup: `sudo cp org.gnome.Vino.gschema.xml.old org.gnome.Vino.gschema.xml`. Re-edit carefully. |
| VNC connection refused | Confirm `vino-server` is running: `ps aux \| grep vino`. Check firewall: `sudo ufw allow 5900`. |
| Black screen over VNC | HDMI dummy plug must be connected. Without it, no framebuffer is created. |
| Wrong password | Re-set: `gsettings set org.gnome.Vino vnc-password $(echo -n 'newpassword'\|base64)`. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with screenshots, client setup for all platforms, and auto-start configuration (reference only)
