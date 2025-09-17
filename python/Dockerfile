#poc_kafka_python
#docker run -it --network POC --rm -v $(pwd):/tmp   poc_kafka_python /bin/bash
from python:3.13-slim
WORKDIR /app
COPY ./carrega_redis.py .
COPY ./requirements.txt .

RUN pip install --upgrade pip && pip install -r /app/requirements.txt
