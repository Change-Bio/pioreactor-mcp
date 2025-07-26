#!/bin/bash
# not included unless it's in the MANIFEST.in

set -x
set -e

export LC_ALL=C

sudo systemctl stop pioreactor_startup_run@logs2slack.service
sudo systemctl disable pioreactor_startup_run@logs2slack.service
