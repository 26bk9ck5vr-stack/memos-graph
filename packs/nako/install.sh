#!/bin/bash
# Nako Pack Installer
# Usage: bash install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_NAME="nako"

echo "Installing Nako pack..."

# Install via memos-graph CLI
memos-graph pack install "$SCRIPT_DIR"

echo "Nako pack installed successfully!"
echo "Run 'memos-graph pack run nako' to start."
