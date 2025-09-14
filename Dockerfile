FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p data
COPY . .

EXPOSE 60000

CMD ["python", "start.py", "-p", "60000,60001"] 