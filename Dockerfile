FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir tzdata
COPY src ./src
COPY server.py config.json ./
CMD ["python", "server.py"]
