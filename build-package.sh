#!/bin/bash
# Build script for att-gateway-check debian package

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse command line arguments
NEW_VERSION=""
AUTO_YES=false
DEPLOY=false
OUTPUT_DIR="."

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        -d|--deploy)
            DEPLOY=true
            shift
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [VERSION] [OPTIONS]"
            echo ""
            echo "Arguments:"
            echo "  VERSION          New version number (e.g., 0.2.0)"
            echo ""
            echo "Options:"
            echo "  -y, --yes       Skip confirmation prompts"
            echo "  -d, --deploy    Deploy to remote repository after build"
            echo "  -o, --output    Output directory for .deb file"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 0.2.0                    # Build version 0.2.0"
            echo "  $0 0.2.0 --yes --deploy     # Build and deploy automatically"
            exit 0
            ;;
        *)
            if [ -z "$NEW_VERSION" ]; then
                NEW_VERSION="$1"
            else
                echo "Error: Unknown argument: $1"
                exit 1
            fi
            shift
            ;;
    esac
done

# Get current version
CURRENT_VERSION=$(cat VERSION)

# If no new version specified, use current
if [ -z "$NEW_VERSION" ]; then
    NEW_VERSION="$CURRENT_VERSION"
    echo "Using current version: $NEW_VERSION"
else
    echo "Updating version: $CURRENT_VERSION -> $NEW_VERSION"

    # Update VERSION file
    echo "$NEW_VERSION" > VERSION

    # Update DEBIAN/control
    sed -i "s/^Version: .*/Version: $NEW_VERSION/" DEBIAN/control

    # Update __init__.py
    sed -i "s/__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" \
        usr/local/lib/python3.11/site-packages/att_gateway/__init__.py

    # Update man page
    sed -i "s/att-gateway-check [0-9.]*\"/att-gateway-check $NEW_VERSION\"/" \
        usr/share/man/man8/att-gateway-check.8

    echo "Version updated in all files"
fi

# Confirm build
if [ "$AUTO_YES" = false ]; then
    echo ""
    read -p "Build att-gateway-check version $NEW_VERSION? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Build cancelled"
        exit 1
    fi
fi

echo ""
echo "============================================================"
echo "Building att-gateway-check $NEW_VERSION"
echo "============================================================"
echo ""

# Run make
make deb

DEB_FILE="att-gateway-check_${NEW_VERSION}_all.deb"

# Move to output directory if specified
if [ "$OUTPUT_DIR" != "." ]; then
    mkdir -p "$OUTPUT_DIR"
    mv "$DEB_FILE" "$OUTPUT_DIR/"
    echo "Package moved to: $OUTPUT_DIR/$DEB_FILE"
    DEB_FILE="$OUTPUT_DIR/$DEB_FILE"
fi

echo ""
echo "============================================================"
echo "Build complete!"
echo "============================================================"
echo "Package: $DEB_FILE"
echo "Size: $(du -h "$DEB_FILE" | cut -f1)"
echo ""

# Offer to deploy
if [ "$DEPLOY" = true ] || [ "$AUTO_YES" = false ]; then
    if [ "$DEPLOY" = false ]; then
        read -p "Deploy to remote repository (proxy)? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Deployment skipped"
            exit 0
        fi
    fi

    echo ""
    echo "============================================================"
    echo "Deploying to remote repository"
    echo "============================================================"
    echo ""

    # Check if proxy is reachable
    if ! ssh -q proxy exit 2>/dev/null; then
        echo "Error: Cannot connect to proxy server"
        exit 1
    fi

    # Create remote pool directory if needed
    ssh proxy "mkdir -p /var/www/projects.thedude.vip/apt/pool/main"

    # Copy package to remote
    echo "Copying package to proxy..."
    scp "$DEB_FILE" proxy:/var/www/projects.thedude.vip/apt/pool/main/

    # Update repository metadata locally (with GPG signing)
    echo "Updating repository metadata..."

    # Create temporary directory for repository work
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT

    # Copy current Packages files from proxy
    echo "  - Fetching current repository state..."
    scp -q proxy:/var/www/projects.thedude.vip/apt/Packages "$TEMP_DIR/" 2>/dev/null || touch "$TEMP_DIR/Packages"

    # Regenerate Packages files on proxy
    echo "  - Regenerating Packages files..."
    ssh proxy "cd /var/www/projects.thedude.vip/apt && dpkg-scanpackages pool/ /dev/null > Packages && gzip -9c Packages > Packages.gz"

    # Download updated Packages files
    scp -q proxy:/var/www/projects.thedude.vip/apt/Packages "$TEMP_DIR/"
    scp -q proxy:/var/www/projects.thedude.vip/apt/Packages.gz "$TEMP_DIR/"

    # Generate Release file locally with correct Label
    echo "  - Generating Release file..."
    cat > "$TEMP_DIR/Release" <<EOF
Origin: Silver Linings, LLC
Label: bad-ips
Suite: stable
Codename: homelab
Architectures: all amd64
Components: main
Description: Homelab APT Repository
Date: $(date -u '+%a, %d %b %Y %H:%M:%S UTC')
MD5Sum:
$(cd "$TEMP_DIR" && for f in Packages Packages.gz; do echo " $(md5sum $f | cut -d' ' -f1) $(stat -c%s $f) $f"; done)
SHA1:
$(cd "$TEMP_DIR" && for f in Packages Packages.gz; do echo " $(sha1sum $f | cut -d' ' -f1) $(stat -c%s $f) $f"; done)
SHA256:
$(cd "$TEMP_DIR" && for f in Packages Packages.gz; do echo " $(sha256sum $f | cut -d' ' -f1) $(stat -c%s $f) $f"; done)
EOF

    # Sign Release file locally with GPG
    echo "  - Signing Release file with GPG..."
    gpg --default-key "Silver Linings, LLC" --armor --detach-sign --yes --output "$TEMP_DIR/Release.gpg" "$TEMP_DIR/Release" 2>/dev/null
    gpg --default-key "Silver Linings, LLC" --clearsign --yes --output "$TEMP_DIR/InRelease" "$TEMP_DIR/Release" 2>/dev/null

    # Upload signed Release files to proxy
    echo "  - Uploading signed Release files..."
    scp -q "$TEMP_DIR/Release" "$TEMP_DIR/Release.gpg" "$TEMP_DIR/InRelease" proxy:/var/www/projects.thedude.vip/apt/

    # Show package count
    PACKAGE_COUNT=$(grep -c '^Package:' "$TEMP_DIR/Packages" || echo "0")
    echo "  ✓ Repository updated ($PACKAGE_COUNT packages)"

    echo ""
    echo "============================================================"
    echo "Deployment complete!"
    echo "============================================================"
    echo ""
    echo "Install on target systems with:"
    echo "  sudo apt update"
    echo "  sudo apt install att-gateway-check"
    echo ""
fi

echo "Done!"
