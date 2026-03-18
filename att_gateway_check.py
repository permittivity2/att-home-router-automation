#!/usr/bin/env python3
"""AT&T BGW320-500 Gateway Configuration Monitor

Checks and restores public subnet and IP allocation settings that AT&T
firmware updates tend to wipe. Designed to run from cron on a Raspberry Pi.

Logs to stdout (pipe through systemd-cat for journalctl integration):
  systemd-cat -t att-gateway-check python3 att_gateway_check.py

View logs:
  journalctl -t att-gateway-check
"""

import hashlib
import logging
import re
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration ────────────────────────────────────────────────────────────

GATEWAY_HOST = "192.168.1.254"
GATEWAY_PASSWORD = "@@65?3@841"

EXPECTED_PUBLIC_SUBNET = {
    "pubsub": "on",
    "ain": "on",
    "pubipaddr": "23.116.91.70",
    "pubmask": "255.255.255.0",
    "pubdhcpstart": "23.116.91.65",
    "pubdhcpend": "23.116.91.69",
    "primpool": "private",
}

# MAC -> expected IP for Fixed Allocation entries
EXPECTED_IP_ALLOCATIONS = {
    "bc:24:11:8f:08:b4": "23.116.91.68",
    "bc:24:11:73:51:b4": "23.116.91.66",
    "90:ec:77:93:b9:c7": "23.116.91.65",
}

# ── Logging ──────────────────────────────────────────────────────────────────

log = logging.getLogger("att-gateway-check")
log.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
log.addHandler(handler)

# ── Gateway class ────────────────────────────────────────────────────────────


class ATTGateway:
    def __init__(self, host, password):
        self.base = f"https://{host}"
        self.password = password
        self.session = requests.Session()
        self.session.verify = False

    def _url(self, path):
        return f"{self.base}/cgi-bin/{path}"

    def _extract_nonce(self, html):
        m = re.search(r'name="nonce"\s+value="([^"]+)"', html)
        if not m:
            raise RuntimeError("Could not extract nonce from page")
        return m.group(1)

    def login(self):
        """Authenticate with the gateway using nonce+MD5 challenge."""
        # First request establishes session cookie
        r = self.session.get(self._url("ipalloc.ha"), allow_redirects=False)
        # Second request gets the login form with nonce
        r = self.session.get(self._url("ipalloc.ha"))
        nonce = self._extract_nonce(r.text)

        # MD5(password + nonce)
        hash_input = self.password + nonce
        hashpwd = hashlib.md5(hash_input.encode()).hexdigest()
        stars = "*" * len(self.password)

        r = self.session.post(
            self._url("login.ha"),
            data={
                "nonce": nonce,
                "password": stars,
                "hashpassword": hashpwd,
                "Continue": "Continue",
            },
            allow_redirects=False,
        )

        if r.status_code != 302 or "login.ha" in r.headers.get("Location", ""):
            raise RuntimeError(
                f"Login failed: status={r.status_code} "
                f"location={r.headers.get('Location', 'none')}"
            )
        log.info("Logged in to gateway")

    def _parse_select_value(self, html, name):
        """Extract the selected value from a <select> element."""
        m = re.search(
            rf'<select[^>]*name="{name}"[^>]*>(.*?)</select>', html, re.DOTALL
        )
        if not m:
            return None
        options_html = m.group(1)
        sel = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', options_html)
        return sel.group(1) if sel else None

    def _parse_input_value(self, html, name):
        """Extract value from an <input> element."""
        m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html)
        if not m:
            m = re.search(rf'value="([^"]*)"[^>]*name="{name}"', html)
        return m.group(1) if m else None

    def _parse_radio_value(self, html, name):
        """Extract the checked radio button value."""
        m = re.search(
            rf'name="{name}"\s+value="([^"]*)"[^>]*checked', html
        )
        if not m:
            m = re.search(
                rf'value="([^"]*)"[^>]*name="{name}"[^>]*checked', html
            )
        return m.group(1) if m else None

    def check_public_subnet(self):
        """Check public subnet settings. Returns (ok, current_values, html)."""
        r = self.session.get(self._url("dhcpserver.ha"))
        html = r.text

        if "Access Code Required" in html:
            raise RuntimeError("Not authenticated - session expired?")

        current = {}
        # Select fields
        for field in ("pubsub", "ain"):
            current[field] = self._parse_select_value(html, field)
        # Text input fields
        for field in ("pubipaddr", "pubmask", "pubdhcpstart", "pubdhcpend"):
            current[field] = self._parse_input_value(html, field)
        # Radio button
        current["primpool"] = self._parse_radio_value(html, "primpool")

        # Log current state
        log.info("Public Subnet current state:")
        all_ok = True
        for field, expected in EXPECTED_PUBLIC_SUBNET.items():
            actual = current.get(field, "MISSING")
            status = "OK" if actual == expected else "MISMATCH"
            if status != "OK":
                all_ok = False
            log.info("  %-15s = %-20s (expected: %-20s) [%s]", field, actual, expected, status)

        return all_ok, current, html

    def fix_public_subnet(self, html):
        """Submit the DHCP form with correct public subnet values."""
        nonce = self._extract_nonce(html)

        # We need to include the private LAN fields too since it's one form
        data = {
            "nonce": nonce,
            # Private LAN (preserve existing values)
            "ipaddr": self._parse_input_value(html, "ipaddr") or "192.168.1.254",
            "ipmask": self._parse_input_value(html, "ipmask") or "255.255.255.0",
            "dhcp": self._parse_select_value(html, "dhcp") or "on",
            "dhcpstart": self._parse_input_value(html, "dhcpstart") or "192.168.1.64",
            "dhcpend": self._parse_input_value(html, "dhcpend") or "192.168.1.253",
            "dhcpday": self._parse_input_value(html, "dhcpday") or "1",
            "dhcphour": self._parse_input_value(html, "dhcphour") or "0",
            "dhcpmin": self._parse_input_value(html, "dhcpmin") or "0",
            "dhcpsec": self._parse_input_value(html, "dhcpsec") or "0",
            # Public Subnet (set to expected values)
            "pubsub": EXPECTED_PUBLIC_SUBNET["pubsub"],
            "ain": EXPECTED_PUBLIC_SUBNET["ain"],
            "pubipaddr": EXPECTED_PUBLIC_SUBNET["pubipaddr"],
            "pubmask": EXPECTED_PUBLIC_SUBNET["pubmask"],
            "pubdhcpstart": EXPECTED_PUBLIC_SUBNET["pubdhcpstart"],
            "pubdhcpend": EXPECTED_PUBLIC_SUBNET["pubdhcpend"],
            "primpool": EXPECTED_PUBLIC_SUBNET["primpool"],
            # Cascaded Router (preserve as off)
            "cr": self._parse_select_value(html, "cr") or "off",
            # Submit
            "Save": "Save",
        }

        log.info("Submitting public subnet fix...")
        r = self.session.post(self._url("dhcpserver.ha"), data=data)

        if "Changes saved" in r.text or r.status_code in (200, 302):
            log.info("Public subnet settings saved successfully")
            return True
        else:
            log.error("Public subnet save may have failed (no 'Changes saved' confirmation)")
            return False

    def check_ip_allocations(self):
        """Check IP allocation table. Returns (ok, current_allocations, html)."""
        r = self.session.get(self._url("ipalloc.ha"))
        html = r.text

        if "Access Code Required" in html:
            raise RuntimeError("Not authenticated - session expired?")

        # Parse the allocation table
        # Each row has: IP/Name, MAC, Status, Allocation Type
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        allocations = {}  # mac -> (ip, status, alloc_type)

        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) >= 4:
                ip = re.sub(r"<[^>]+>", "", cells[0]).strip()
                mac = re.sub(r"<[^>]+>", "", cells[1]).strip().lower()
                status = re.sub(r"<[^>]+>", "", cells[2]).strip()
                alloc_type = re.sub(r"<[^>]+>", "", cells[3]).strip()
                if mac:
                    allocations[mac] = (ip, status, alloc_type)

        # Log full allocation table
        log.info("IP Allocation table:")
        for mac, (ip, status, alloc_type) in sorted(allocations.items()):
            log.info("  %-20s  %-17s  %-5s  %s", ip, mac, status, alloc_type)

        # Check expected allocations
        missing = []
        all_ok = True
        log.info("Expected IP allocations:")
        for mac, expected_ip in EXPECTED_IP_ALLOCATIONS.items():
            mac_lower = mac.lower()
            if mac_lower in allocations:
                ip, status, alloc_type = allocations[mac_lower]
                if alloc_type == "Fixed Allocation":
                    log.info("  %s (%s) -> %s [OK]", expected_ip, mac, alloc_type)
                else:
                    log.warning(
                        "  %s (%s) -> %s (expected Fixed Allocation) [NEEDS FIX]",
                        expected_ip, mac, alloc_type,
                    )
                    missing.append(mac)
                    all_ok = False
            else:
                log.warning("  %s (%s) -> NOT FOUND in table [NEEDS FIX]", expected_ip, mac)
                missing.append(mac)
                all_ok = False

        return all_ok, missing, html

    def allocate_ip(self, mac, html):
        """Allocate a specific MAC address via the IP Allocation form."""
        nonce = self._extract_nonce(html)
        button_name = f"Allocate_{mac}"

        log.info("Allocating IP for MAC %s (button: %s)...", mac, button_name)
        r = self.session.post(
            self._url("ipalloc.ha"),
            data={"nonce": nonce, button_name: "Allocate"},
        )

        if "Fixed Allocation" in r.text or "Changes saved" in r.text:
            log.info("Successfully allocated IP for %s", mac)
            return True, r.text
        else:
            log.error("Allocation for %s may have failed", mac)
            return False, r.text

    def run(self):
        """Main check-and-fix routine. Returns exit code."""
        exit_code = 0

        try:
            self.login()
        except Exception as e:
            log.error("Login failed: %s", e)
            return 2

        # Check and fix public subnet
        try:
            subnet_ok, current, html = self.check_public_subnet()
            if not subnet_ok:
                log.warning("Public subnet misconfigured - attempting fix")
                if self.fix_public_subnet(html):
                    # Verify the fix
                    subnet_ok2, _, _ = self.check_public_subnet()
                    if subnet_ok2:
                        log.info("Public subnet fix verified")
                        exit_code = max(exit_code, 1)
                    else:
                        log.error("Public subnet fix did not take effect")
                        exit_code = 2
                else:
                    exit_code = 2
        except Exception as e:
            log.error("Public subnet check failed: %s", e)
            exit_code = 2

        # Check and fix IP allocations
        try:
            alloc_ok, missing_macs, html = self.check_ip_allocations()
            if not alloc_ok:
                for mac in missing_macs:
                    log.warning("IP allocation missing for %s - attempting fix", mac)
                    success, html = self.allocate_ip(mac, html)
                    if not success:
                        exit_code = 2
                    else:
                        exit_code = max(exit_code, 1)

                # Verify
                if exit_code != 2:
                    alloc_ok2, still_missing, _ = self.check_ip_allocations()
                    if alloc_ok2:
                        log.info("IP allocation fix verified")
                    else:
                        log.error(
                            "IP allocation fix incomplete, still missing: %s",
                            still_missing,
                        )
                        exit_code = 2
        except Exception as e:
            log.error("IP allocation check failed: %s", e)
            exit_code = 2

        if exit_code == 0:
            log.info("All checks passed - gateway configuration is correct")
        elif exit_code == 1:
            log.warning("Fixes were applied successfully")
        else:
            log.error("Some checks/fixes failed")

        return exit_code


if __name__ == "__main__":
    gw = ATTGateway(GATEWAY_HOST, GATEWAY_PASSWORD)
    sys.exit(gw.run())
