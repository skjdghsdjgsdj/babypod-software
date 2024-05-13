#!/bin/bash
if which mpy-cross &> /dev/null -ne 0; then
	echo "No mpy-cross in path; build one using these instructions: https://learn.adafruit.com/building-circuitpython/build-circuitpython" 1>&2
	exit 1
fi

OUTPUT_PATH="/Volumes/CIRCUITPY"

if [ ! -d "$OUTPUT_PATH" ]; then
	echo "$OUTPUT_PATH not mounted" 1>&2
	exit 1
fi

mkdir -p lib
find . -maxdepth 1 -type f -not -name 'code.py' -name '*.py' | while read -r SOURCE_FILE; do
	BASENAME=$(basename "$SOURCE_FILE")
	MPY_NAME="lib/${BASENAME%.py}.mpy"
	BUILD_COMMAND="mpy-cross $BASENAME -O9 -o $MPY_NAME"

	if [[ -z "$1" || "$1" == "${BASENAME%.py}" ]]; then
		echo -n "Building $BASENAME..."
		$BUILD_COMMAND
		if [ $? -ne 0 ]; then
			echo "Build failed" 1>&2
			exit 1
		fi

		echo -n "deploying..."
		cp "$MPY_NAME" "$OUTPUT_PATH/lib/"
		if [ $? -ne 0 ]; then
			echo "Failed to copy built library $MPY_NAME to $OUTPUT_PATH/lib"
		fi

		echo "done"
	else
		echo "Skipping building $SOURCE_FILE"
	fi
done

if [[ -z "$1" || "$1" == "code" ]]; then
	echo -n "Deploying code.py..."
	cp code.py $OUTPUT_PATH/
	echo "done"
fi
