FROM python:3-alpine

RUN pip install docopt influxdb

ADD main.py main.py

ENTRYPOINT ["python3", "-u", "main.py"]
