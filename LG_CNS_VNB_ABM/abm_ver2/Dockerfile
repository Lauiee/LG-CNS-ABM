FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py simulate.py model.py agents.py tasks.py ./
COPY dashboard.html ./

ENV PORT=8765
EXPOSE 8765

CMD ["python", "server.py"]
