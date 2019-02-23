#!/bin/sh -eu

sleep 3

function fail() {
    echo "${FAILURE_STRING}" >> ${LOG_FILE} 2>&1
}

trap fail EXIT

until [ -f "${LOG_FILE}" ]; do
    sleep 1
done

if grep "${FAILURE_STRING}" ${LOG_FILE}; then
    echo "exiting due to previous stage failure..."
    exit 0
fi

(
    echo "starting"
    sleep 1
    echo "some stuff happening here..."
    sleep 1
    echo "some more stuff happening here..."
) >> ${LOG_FILE} 2>&1

trap : 0
echo ${COMPLETION_STRING} >> ${LOG_FILE} 2>&1
