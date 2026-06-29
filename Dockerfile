FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --extra ai

COPY src/ ./src/
COPY words/ ./words/
COPY units/ ./units/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["patlint-api", "--host", "0.0.0.0", "--no-open"]
