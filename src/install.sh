#!/bin/bash

sudo apt update

# Install required tools
sudo apt install -y ipmitool hddtemp lm-sensors

# Install Python modules
sudo python3 -m pip install minilog

# Copy service and application
sudo cp ipmi-fan-controller.py /usr/local/bin/ipmi-fan-controller.py
sudo cp ipmi-fan-controller.service /etc/systemd/system/ipmi-fan-controller.service

# Reload service files
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable ipmi-fan-controller.service
sudo systemctl start ipmi-fan-controller.service
