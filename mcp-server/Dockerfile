FROM python:3.12-slim

WORKDIR /app

COPY mcp-server/requirements.txt mcp-server/requirements.txt
RUN pip install --no-cache-dir -r mcp-server/requirements.txt

COPY commons/ commons/
COPY configs/ configs/
COPY mcp-server/ mcp-server/
COPY run_mcp_server.py .

ENV PYTHONPATH=.

EXPOSE 8001

CMD ["uvicorn", "run_mcp_server:app", "--host", "0.0.0.0", "--port", "8001"]
