#!/usr/bin/env bash

#include id and url
source "${HOME}/we4bee.profile"

DIRECTORY="/tmp/we4bee/audio"
LOG_FILE="/var/log/we4bee/sound.log"
CHANNEL="audio"
FEED="we4bee-measurements-binary"
NAME="overall"
EXTENSION="flac"

LOCATION="${HOME}/code-we4bee-sensor_network/misc"

shopt -s nullglob

for f in "${DIRECTORY}"/*."${EXTENSION}"; do
  ff=$(basename "${f}")
  ts=${ff%.*}
  if [[ $(bash "${LOCATION}/check_connection.sh") -eq 0 ]]; then
    status=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Expect:" -H "meta.sourceId: ${SOURCE_ID}" -H "meta.feeds: ${FEED}" -F "channel=${CHANNEL}" -F "name=${NAME}" -F "extension=${EXTENSION}" -F "timestamp=${ts}" -F "multipartFile=@${f}" --user "${WE4BEE_USER}:${WE4BEE_PASSWORD}" "${WE4BEE_BINARY_URL}")
    if [[ "${status}" -eq 200 ]]; then
      touch "${LOG_FILE}"
    fi
  fi
  rm "${f}"
done
