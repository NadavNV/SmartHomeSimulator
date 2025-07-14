FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY *.py .
COPY config/ config/
COPY devices/ devices/
COPY validation/ validation/

CMD ["python", "main.py"]