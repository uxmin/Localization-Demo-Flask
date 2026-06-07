FROM python:3.12-slim

WORKDIR /src

RUN apt-get update \
    && apt-get install -y python3-dev gcc g++ libmagic1 \
    && pip install --upgrade pip

COPY . /src

COPY ./requirements.txt /src/requirements.txt
RUN pip3 install --no-cache-dir --upgrade -r /src/requirements.txt

ENTRYPOINT ["sh", "run.sh"]