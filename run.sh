#!/bin/bash

init() {
if [ -e venv/ ]; then
	echo "venv directory exists, remove before trying to init"
	exit	
fi

python3 -m venv venv
venv/bin/pip install -r requirements.txt

}

run(){
venv/bin/python3 -m uvicorn app:app --host $HOST --port $PORT
}

if [ "$PORT" = "" ]; then
	PORT=5001
fi
if [ "$HOST" = "" ]; then
	HOST="0.0.0.0"
fi


case "$1" in
	"init")
		init
		;;
	"run")
		run
		;;
	*)
		echo "Usage: ./run.sh init|run"
		exit
		;;
esac


