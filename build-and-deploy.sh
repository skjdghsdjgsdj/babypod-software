#!/bin/bash
mkdir -p lib
find . -maxdepth 1 -type f -not -name 'code.py' -name '*.py' | while read -r SOURCE_FILE; do
	BASENAME=$(basename "$SOURCE_FILE")
	MPY_NAME="lib/${BASENAME%.py}.mpy"
	BUILD_COMMAND="./mpy-cross $BASENAME -O9 -o $MPY_NAME"

	echo "$BUILD_COMMAND"
	$BUILD_COMMAND
	if [ $? -ne 0 ]; then
		echo "Build failed" 1>&2
		exit 1
	fi
done

cp -v lib/*.mpy /Volumes/CIRCUITPY/lib/
cp -v code.py /Volumes/CIRCUITPY/
