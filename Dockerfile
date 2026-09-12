FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG APP_PORT=8765
ENV PORT=${APP_PORT}
ENV HOST=0.0.0.0
ENV PROMPT_GEN_NO_BROWSER=1
EXPOSE ${APP_PORT}

CMD ["python", "launch.py"]