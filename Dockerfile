FROM python:3.12

RUN apt update && apt install -y && apt clean

COPY ./requirements.txt /app/requirements.txt
RUN pip install -U pip --no-cache-dir && pip install -r /app/requirements.txt --no-cache-dir

COPY . /app
WORKDIR /app

# RUN adduser user
# USER user