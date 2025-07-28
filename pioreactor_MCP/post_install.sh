#!/bin/bash
# this isn't included unless it's in the MANIFEST.in

set -x
set -e

export LC_ALL=C

sudo systemctl enable pioreactor_startup_run@logs2slack.service
