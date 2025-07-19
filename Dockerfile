FROM python:3.13-alpine

WORKDIR /app
COPY requirements.txt .

RUN apk add --no-cache git
RUN pip install --no-cache -r requirements.txt

COPY *.py .
COPY config/ config/
COPY devices/ devices/
COPY config/ config/
COPY validation/ validation/
COPY test/ test/
COPY services/ services/
COPY core/ core/

CMD ["python", "main.py"]