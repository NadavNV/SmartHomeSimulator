FROM python:3.14.0b3-alpine

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY *.py .

COPY data.json .

CMD ["python", "main.py"]