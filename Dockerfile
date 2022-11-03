FROM python:3.10-slim-buster

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
RUN apt-get update &&\
    apt-get -y install libpq-dev gcc
RUN pip install --upgrade pip
COPY . .
RUN pip3 install -r requirements.txt
RUN python3 -m venv venv
