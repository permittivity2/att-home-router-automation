.PHONY: deb clean install help

PACKAGE_NAME = att-gateway-check
VERSION = $(shell cat VERSION)
DEB_NAME = $(PACKAGE_NAME)_$(VERSION)_all.deb
BUILD_DIR = $(CURDIR)/build
INSTALL_ROOT = $(BUILD_DIR)/$(PACKAGE_NAME)

help:
	@echo "Available targets:"
	@echo "  make deb     - Build debian package"
	@echo "  make clean   - Clean build artifacts"
	@echo "  make install - Install package (requires root)"

deb: clean
	@echo "Building $(DEB_NAME)..."

	# Create build directory structure
	mkdir -p $(INSTALL_ROOT)/DEBIAN
	mkdir -p $(INSTALL_ROOT)/usr/local/sbin
	mkdir -p $(INSTALL_ROOT)/usr/local/lib/python3.11/site-packages/att_gateway/handlers
	mkdir -p $(INSTALL_ROOT)/usr/local/share/att-gateway-check
	mkdir -p $(INSTALL_ROOT)/usr/share/doc/$(PACKAGE_NAME)
	mkdir -p $(INSTALL_ROOT)/usr/share/man/man8
	mkdir -p $(INSTALL_ROOT)/etc/att_gateway
	mkdir -p $(INSTALL_ROOT)/etc/systemd/system
	mkdir -p $(INSTALL_ROOT)/etc/bash_completion.d

	# Copy DEBIAN control files
	cp -r DEBIAN/* $(INSTALL_ROOT)/DEBIAN/
	chmod 755 $(INSTALL_ROOT)/DEBIAN/postinst
	chmod 755 $(INSTALL_ROOT)/DEBIAN/prerm
	chmod 755 $(INSTALL_ROOT)/DEBIAN/postrm

	# Copy binary
	cp usr/local/sbin/att-gateway-check $(INSTALL_ROOT)/usr/local/sbin/
	chmod 755 $(INSTALL_ROOT)/usr/local/sbin/att-gateway-check

	# Copy Python package
	cp -r usr/local/lib/python3.11/site-packages/att_gateway/* \
		$(INSTALL_ROOT)/usr/local/lib/python3.11/site-packages/att_gateway/
	find $(INSTALL_ROOT)/usr/local/lib/python3.11/site-packages/att_gateway -type f -exec chmod 644 {} \;
	find $(INSTALL_ROOT)/usr/local/lib/python3.11/site-packages/att_gateway -type d -exec chmod 755 {} \;

	# Copy shared data
	cp usr/local/share/att-gateway-check/firmware_versions.json \
		$(INSTALL_ROOT)/usr/local/share/att-gateway-check/
	chmod 644 $(INSTALL_ROOT)/usr/local/share/att-gateway-check/firmware_versions.json

	# Copy configuration template
	cp etc/att_gateway/att_gateway.conf.template $(INSTALL_ROOT)/etc/att_gateway/
	chmod 644 $(INSTALL_ROOT)/etc/att_gateway/att_gateway.conf.template

	# Copy systemd units
	cp etc/systemd/system/att-gateway-check.service $(INSTALL_ROOT)/etc/systemd/system/
	cp etc/systemd/system/att-gateway-check.timer $(INSTALL_ROOT)/etc/systemd/system/
	chmod 644 $(INSTALL_ROOT)/etc/systemd/system/att-gateway-check.service
	chmod 644 $(INSTALL_ROOT)/etc/systemd/system/att-gateway-check.timer

	# Copy bash completion
	cp etc/bash_completion.d/att-gateway-check $(INSTALL_ROOT)/etc/bash_completion.d/
	chmod 644 $(INSTALL_ROOT)/etc/bash_completion.d/att-gateway-check

	# Copy documentation
	cp VERSION $(INSTALL_ROOT)/usr/share/doc/$(PACKAGE_NAME)/
	cp README.md $(INSTALL_ROOT)/usr/share/doc/$(PACKAGE_NAME)/
	chmod 644 $(INSTALL_ROOT)/usr/share/doc/$(PACKAGE_NAME)/*

	# Copy and compress man page
	cp usr/share/man/man8/att-gateway-check.8 $(INSTALL_ROOT)/usr/share/man/man8/
	gzip -9 $(INSTALL_ROOT)/usr/share/man/man8/att-gateway-check.8

	# Build package
	dpkg-deb --build $(INSTALL_ROOT) $(DEB_NAME)

	@echo ""
	@echo "Package built: $(DEB_NAME)"
	@echo ""

clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)
	rm -f *.deb
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "Clean complete"

install:
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "Error: Installation requires root privileges"; \
		echo "Please run: sudo make install"; \
		exit 1; \
	fi
	@if [ ! -f "$(DEB_NAME)" ]; then \
		echo "Error: Package not found. Run 'make deb' first"; \
		exit 1; \
	fi
	@echo "Installing $(DEB_NAME)..."
	dpkg -i $(DEB_NAME)
	@echo "Installation complete"
