FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_INDEX=1
WORKDIR /app
COPY wheels/ /wheels/
RUN python -m pip install --no-index --find-links=/wheels -r /wheels/requirements.txt
COPY offlineknowledge/ /app/offlineknowledge/
COPY LICENSE UPSTREAM.md THIRD-PARTY.md /app/
USER 10001:10001
ENTRYPOINT ["python", "-m", "offlineknowledge.server"]
