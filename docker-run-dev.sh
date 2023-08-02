#!/bin/bash

# Change directory to the current script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

docker run --rm -it \
	-e SYSTEM_MESSAGE="This is an example!" \
	-e HEARTBEAT_INTERVAL=5000 \
	-p 8184:8184 \
	-v "$(pwd):/mnt" \
	gpt4all-box:dev
