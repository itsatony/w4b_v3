#!/usr/bin/env bash

SLEEP_TIME=5
LOCATION="${HOME}/code-we4bee-sensor_network"

while :; do
  python3 "${LOCATION}/collector.py"
  sleep ${SLEEP_TIME}
done
