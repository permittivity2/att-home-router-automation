# AT&T Home Router Automation

Automated configuration management for AT&T BGW320-500 residential gateways.

## ⚠️ Security Notice

**NEVER commit your actual configuration files or credentials to git!**

- Real passwords go in `/etc/att_gateway/att_gateway.conf` (NOT in git)
- Real IP addresses stay in your local config (NOT in git)
- The `.gitignore` is configured to protect sensitive files

## Problem

AT&T residential gateways (BGW320-500) have a nasty habit of **losing configuration during firmware updates**. Settings like:
- Public subnet configuration
- Fixed IP allocations
- Custom DHCP settings

...get wiped out every time AT&T pushes a firmware update, requiring manual reconfiguration.

## Solution

This tool:
1. **Monitors** gateway configuration continuously
2. **Detects** when settings change (firmware updates)
3. **Automatically restores** your intended configuration
4. **Backs up** complete gateway state
5. **Adapts** to different firmware versions

## Features

- ✅ **Firmware version detection** - Automatically adapts to different AT&T firmware versions
- ✅ **Auto-fix mode** - Automatically corrects misconfigurations
- ✅ **Configuration backup** - Full gateway state backups (coming soon)
- ✅ **Selective restore** - Restore specific settings or everything (coming soon)
- ✅ **Systemd integration** - Runs as a proper service with timer
- ✅ **Comprehensive logging** - All changes logged to journald

## Architecture

### Version-Aware Design

AT&T changes the gateway interface with firmware updates. This tool handles that:

```
Firmware 6.34.7 → Handler_6_34 → Known page paths, field names
Firmware 7.x.x → Handler_7_x → Updated for new interface
Unknown version → Default Handler → Best-effort attempt
```

When AT&T breaks things with an update:
1. Tool detects new firmware version
2. Logs prominently and takes automatic backup
3. Attempts to work with default handler
4. New version handler can be added quickly

### Modular Design

```
att_gateway/
├── gateway.py       # Authentication, session management
├── version.py       # Firmware detection
├── handlers/        # Version-specific logic
│   ├── base.py      # Abstract interface
│   ├── v6_34.py     # Current firmware
│   └── default.py   # Fallback
├── parser.py        # HTML parsing (BeautifulSoup)
├── config.py        # INI configuration
├── checks.py        # Monitor & auto-fix
├── backup.py        # Backup logic (coming)
└── restore.py       # Restore logic (coming)
```

## Installation

### From Debian Package (Recommended)

```bash
# Add apt repository
echo "deb https://projects.thedude.vip/apt/ stable main" | \
  sudo tee /etc/apt/sources.list.d/thedude.list

# Add GPG key
curl -fsSL https://projects.thedude.vip/apt/gpg.key | sudo apt-key add -

# Install
sudo apt update
sudo apt install att-gateway-check
```

### Configuration

```bash
# Copy template
sudo cp /etc/att_gateway/att_gateway.conf.template /etc/att_gateway/att_gateway.conf

# Edit with your settings
sudo nano /etc/att_gateway/att_gateway.conf

# Set permissions
sudo chmod 640 /etc/att_gateway/att_gateway.conf
sudo chown root:att-gateway /etc/att_gateway/att_gateway.conf
```

**Required settings:**
- Gateway password
- Public subnet IP addresses
- MAC → IP mappings for fixed allocations

### Verify Setup

```bash
# Check systemd timer is active
systemctl status att-gateway-check.timer

# View logs
journalctl -u att-gateway-check.service

# Manual test run
sudo att-gateway-check check

# View man page
man att-gateway-check
```

## Usage

### Check Mode (Automatic)

Runs every 30 minutes via systemd timer:

```bash
# View timer status
systemctl list-timers att-gateway-check.timer

# Trigger manual run
sudo systemctl start att-gateway-check.service

# Follow logs
journalctl -u att-gateway-check.service -f
```

### Manual Commands

```bash
# Check configuration (no auto-fix)
att-gateway-check check --no-fix

# Dry-run (show what would change)
att-gateway-check check --dry-run

# Show firmware version and compatibility
att-gateway-check gateway-info

# Show program version
att-gateway-check version
```

### Future Commands (Coming Soon)

```bash
# Backup current configuration
att-gateway-check backup

# List available backups
att-gateway-check list-backups

# Restore from latest backup
att-gateway-check restore

# Restore specific backup
att-gateway-check restore --backup 2026-03-17-103000

# Dry-run restore (preview changes)
att-gateway-check restore --dry-run

# Discover all gateway pages
att-gateway-check discover
```

## Configuration File Format

INI format with sections:

```ini
[gateway]
host = 192.168.1.254
password = your-actual-password

[check]
enabled = true
auto_fix = true

[check:public_subnet]
enabled = true
pubipaddr = your.public.ip.address
pubdhcpstart = your.public.ip.start
pubdhcpend = your.public.ip.end
# ... more settings

[check:ip_allocations]
enabled = true
device:mac:address = device.ip.address
# ... more devices
```

See `att_gateway.conf.template` for full documentation.

## Exit Codes

- `0` - All checks passed, no issues found
- `1` - Issues found and fixes were applied successfully
- `2` - Errors occurred, some checks/fixes failed

## Development Status

### ✅ Implemented (v0.1.0)

- [x] Core gateway client with authentication
- [x] Firmware version detection (tested with 6.34.7)
- [x] Version-specific handler architecture
- [x] BeautifulSoup-based HTML parsing
- [x] Configuration management (INI format)
- [x] Check mode with auto-fix
  - [x] Public subnet monitoring
  - [x] IP allocation monitoring

### 🚧 In Progress

- [ ] Backup mode (comprehensive configuration export)
- [ ] Restore mode (selective and full restore)
- [ ] Page discovery (find all configuration pages)
- [ ] Systemd service and timer units
- [ ] Debian packaging
- [ ] Man page documentation
- [ ] Comprehensive README

### 📋 Planned

- [ ] Notification support (email, webhook)
- [ ] Web UI for viewing status/backups
- [ ] Multiple gateway support
- [ ] Configuration templates for common setups
- [ ] Automated testing with mock gateway

## Tested Firmware Versions

- **6.34.7** (March 2026) - ✅ Fully tested and supported

Report your firmware version to help expand compatibility!

## Contributing

Contributions welcome! Especially:
- Testing on different firmware versions
- New firmware version handlers
- Bug reports and fixes
- Documentation improvements
- Feature requests

Please open issues at: https://github.com/permittivity2/att-home-router-automation/issues

## License

MIT License - See LICENSE file

## Security

- Never commit your actual config files
- Passwords stored locally only
- Config files have restrictive permissions (640)
- Service runs as non-root user

Report security issues privately to: gardner@homelab

## Credits

Created by Gardner (gardner@homelab)

Built with:
- Python 3
- BeautifulSoup4 for HTML parsing
- Requests for HTTP
- Configparser for INI files
