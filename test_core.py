#!/usr/bin/env python3
"""Test core functionality of att_gateway modules"""

import logging
import sys
import os

# Add module path for testing before installation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'usr/local/lib/python3.11/site-packages'))

from att_gateway import gateway, version, checks
from att_gateway.config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s %(message)s',
    stream=sys.stdout
)

def main():
    print("=" * 60)
    print("Testing AT&T Gateway Core Modules")
    print("=" * 60)

    # Test 1: Gateway connection and authentication
    print("\n[1] Testing gateway authentication...")
    gw = gateway.ATTGateway(
        host="192.168.1.254",
        password="@@65?3@841"
    )

    try:
        gw.login()
        print(f"✓ Authenticated successfully")
        print(f"✓ Firmware version: {gw.firmware_version}")
        print(f"✓ Handler: {gw.handler.__class__.__name__}")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        return 1

    # Test 2: DHCP configuration parsing
    print("\n[2] Testing DHCP configuration parsing...")
    try:
        dhcp_config = gw.get_dhcp_config()
        print(f"✓ DHCP config parsed")
        print(f"  Private LAN IP: {dhcp_config['private_lan']['ipaddr']}")
        print(f"  Public subnet enabled: {dhcp_config['public_subnet']['pubsub']}")
        print(f"  Public IP: {dhcp_config['public_subnet']['pubipaddr']}")
    except Exception as e:
        print(f"✗ DHCP parsing failed: {e}")
        return 1

    # Test 3: IP allocation parsing
    print("\n[3] Testing IP allocation parsing...")
    try:
        ipalloc = gw.get_ip_allocations()
        print(f"✓ IP allocations parsed")
        print(f"  Total allocations: {len(ipalloc['allocations'])}")
        for mac, data in list(ipalloc['allocations'].items())[:3]:
            print(f"    {data['ip']:15s}  {mac:17s}  {data['allocation_type']}")
        if len(ipalloc['allocations']) > 3:
            print(f"    ... and {len(ipalloc['allocations']) - 3} more")
    except Exception as e:
        print(f"✗ IP allocation parsing failed: {e}")
        return 1

    # Test 4: Version detection
    print("\n[4] Testing version detection...")
    try:
        version_info = version.load_version_registry()
        print(f"✓ Version registry loaded")
        print(f"  Supported versions: {len(version_info['supported_versions'])}")

        handler_name, info = version.match_version_to_handler(gw.firmware_version)
        if handler_name:
            print(f"✓ Version {gw.firmware_version} matched to {handler_name}")
        else:
            print(f"⚠ Version {gw.firmware_version} not matched (using default)")
    except Exception as e:
        print(f"✗ Version detection failed: {e}")
        return 1

    # Test 5: Configuration parsing (if config exists)
    print("\n[5] Testing configuration parsing...")
    config_path = "etc/att_gateway/att_gateway.conf.template"
    if os.path.exists(config_path):
        try:
            # For testing, we'll use the template
            cfg = Config(config_path)
            cfg.load()
            print(f"✓ Config loaded from template")
            print(f"  Gateway host: {cfg.get_gateway_host()}")
            print(f"  Check enabled: {cfg.is_check_enabled()}")
            print(f"  Auto-fix enabled: {cfg.is_auto_fix_enabled()}")
        except Exception as e:
            print(f"⚠ Config parsing failed (expected for template): {e}")
    else:
        print(f"⚠ Config template not found at {config_path}")

    print("\n" + "=" * 60)
    print("✓ All core tests passed!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
