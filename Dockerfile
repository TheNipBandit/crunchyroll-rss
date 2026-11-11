FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir tzdata
# Optional: Crunchyroll's own calendar. If this fails, the server still runs on AniList alone.
RUN pip install --no-cache-dir https://github.com/PD-Codes/crunchyroll-api/archive/HEAD.zip || echo "crunchyroll-api not installed"
COPY src ./src
COPY server.py config.json ./
CMD ["python", "server.py"]
