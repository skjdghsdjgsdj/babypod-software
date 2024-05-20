#!/bin/bash
which mpy-cross &> /dev/null
if [ $? -ne 0 ]; then
	echo "No mpy-cross in path; build one using these instructions: https://learn.adafruit.com/building-circuitpython/build-circuitpython" 1>&2
	exit 1
fi

echo -n "Getting version info..."
echo "" > version.py
which git &> /dev/null
if [ $? -eq 0 ]; then
  GIT_STATUS=$(git status --porcelain)
  if [ $? -eq 0 ]; then
    if [ -z "$GIT_STATUS" ]; then
      GIT_HASH=$(git rev-parse --short HEAD)
      if [ $? -eq 0 ]; then
        echo "BABYPOD_VERSION = \"$GIT_HASH\"" > version.py
        echo "done ($GIT_HASH)"
      else
        echo "Failed to get git short hash; not including versioning info" 1>&2
      fi
    else
      echo "done (dirty)"
    fi
  else
    echo "Failed to get git status; not including versioning info" 1>&2
  fi
else
  echo "git not found; not including versioning info" 1>&2
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
		# shellcheck disable=SC2181
		if [ $? -ne 0 ]; then
			echo "Build failed" 1>&2
			exit 1
		fi

		echo -n "deploying..."
		cp "$MPY_NAME" "$OUTPUT_PATH/lib/"
		# shellcheck disable=SC2181
		if [ $? -ne 0 ]; then
			echo "Failed to copy built library $MPY_NAME to $OUTPUT_PATH/lib" 1>&2
			exit 1
		fi

		echo "done"
	else
		echo "Skipping building $SOURCE_FILE"
	fi
done

if [[ -z "$1" || "$1" == "code" ]]; then
	echo -n "Deploying code.py..."
	cp code.py $OUTPUT_PATH/
	if [ $? -ne 0 ]; then
	  echo "failed to copy code.py to $OUTPUT_PATH" 1>&2
	  exit 1
	fi
	echo "done"
fi

echo -n "Deploying version info..."
cp version.py $OUTPUT_PATH/
if [ $? -ne 0 ]; then
  echo "failed to copy version info" 1>&2
else
  echo "done"
fi

rm version.py 2>/dev/null