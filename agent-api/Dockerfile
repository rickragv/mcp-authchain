FROM node:22-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY agent-api/requirements.txt agent-api/requirements.txt
RUN pip install --no-cache-dir -r agent-api/requirements.txt

COPY commons/ commons/
COPY configs/ configs/
COPY agent-api/ agent-api/
COPY run_agent_api.py .

# Frontend served by FastAPI on same port
COPY --from=frontend-build /frontend/dist /app/static

ENV PYTHONPATH=.

EXPOSE 8000

CMD ["uvicorn", "run_agent_api:app", "--host", "0.0.0.0", "--port", "8000"]
