#!/usr/bin/env bash

DIRECTORY=/tmp/we4bee/video
DESTINATION=/data/we4bee/video
DURATION=10
TYPE="gpu"

for f in ${DIRECTORY}/*.mkv; do
  dest_f=$(basename ${f})
  sh ./camera_compression.sh ${TYPE} ${f} ${DESTINATION}/${dest_f} ${DURATION}
  rm ${f}
  python3 redis_writer.py ${DESTINATION}/${dest_f}
done
