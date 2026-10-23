---
name: jetson-pc-wired-share
description: Temporarily share a Linux PC's internet connection to a Jetson over Ethernet using NetworkManager while preserving an existing static-IP SSH link. Use when the user asks to let a directly connected Jetson access the internet through the PC, or to start, verify, or stop that temporary sharing.
---

# Jetson PC wired internet sharing

Use a separate, non-autoconnecting NetworkManager profile on the PC. Keep the
original wired profile intact so the operation is easy to reverse. Never put a
sudo or SSH password in this skill, a connection profile, a script, or a log.

## Start sharing

1. Inspect before changing anything:

   - `nmcli device status`, active connections, `ip -br addr`, and `ip route`.
   - `ip route get <jetson-ip>` to identify the PC interface carrying SSH.
   - The Jetson's interface, address, routes, and DNS over the existing SSH link.
   - Confirm the PC has a working upstream/default route on a different interface.

2. Determine the downstream PC address:

   - If the Jetson already has a static address and SSH uses the wired subnet,
     preserve the PC's existing address and subnet. This avoids losing SSH.
   - Otherwise choose an unused RFC1918 `/24` that does not overlap any PC or
     Jetson route; NetworkManager's usual `10.42.0.1/24` is acceptable only after
     checking for conflicts.

3. Create or update a profile named `jetson-wired-share` on the downstream
   interface. Set `connection.autoconnect no`, `ipv4.method shared`, the chosen
   `ipv4.addresses`, `ipv4.never-default yes`, and `ipv6.method disabled`. Then
   activate it. Do not edit or delete the original wired profile. Example shape:

   ```bash
   sudo nmcli connection add type ethernet \
     ifname <pc-wired-interface> con-name jetson-wired-share autoconnect no \
     ipv4.method shared ipv4.addresses <pc-address/cidr> \
     ipv4.never-default yes ipv6.method disabled
   sudo nmcli connection up jetson-wired-share
   ```

   If that profile already exists, use `nmcli connection modify` instead of
   creating a duplicate. Warn that activation may briefly flap the wired link.

4. Configure the Jetson without making its static profile persistent unless the
   user explicitly asks. For an already-static Jetson, add a runtime route:

   ```bash
   sudo ip route replace default via <pc-wired-ip> dev <jetson-interface> metric 100
   ```

   Retain any unrelated routes. If DNS is not already usable, set runtime DNS on
   that interface with `resolvectl dns <interface> <pc-wired-ip>` when available.
   If split DNS (commonly Tailscale) still captures public lookups, also use
   `resolvectl domain <interface> '~.'` so the wired link routes ordinary DNS.
   For a DHCP-configured Jetson, renew DHCP instead.

5. Verify from the Jetson, in order:

   - ping the PC's downstream address;
   - ping a public IP;
   - resolve a public hostname;
   - make a short HTTPS request.

   Report the active profile, PC/Jetson addresses, route, and observed test
   results. Do not claim success based only on a NetworkManager status message.

NetworkManager `ipv4.method shared` owns DHCP/DNS forwarding and NAT. If it does
not work, inspect NetworkManager logs, IP forwarding, and nftables before making
additional changes. Do not disable the host firewall wholesale.

## Stop sharing

Remove only the runtime Jetson route added by this workflow, deactivate
`jetson-wired-share`, and reactivate the original wired profile discovered at
the start:

```bash
sudo ip route del default via <pc-wired-ip> dev <jetson-interface> metric 100
sudo resolvectl revert <jetson-interface>
sudo nmcli connection down jetson-wired-share
sudo nmcli connection up <original-wired-profile>
```

The share profile may remain saved for reuse because it has autoconnect disabled.
Delete it only when the user asks. Recheck the original PC-to-Jetson SSH route
after restoration.
