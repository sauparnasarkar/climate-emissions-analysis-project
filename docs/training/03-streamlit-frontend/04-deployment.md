# Deployment

> Part of the [Streamlit curriculum](00-index.md). This document covers Streamlit Community
> Cloud, containerized deployment, and secrets management.

## 1. Streamlit Community Cloud

The path of least resistance for a Streamlit app is
[Streamlit Community Cloud](https://streamlit.io/cloud) — connect a GitHub repository
containing the app, point it at the entry-point script, and the platform builds and hosts it
for you (free for public repositories). This matches Streamlit's whole value proposition
(§1 of [Core Concepts](01-core-concepts.md#1-what-streamlit-is-and-its-core-mental-model)):
the fastest possible path from working code to a shareable, running app, with essentially no
deployment engineering required.

## 2. Containerized deployment

For deployment outside Streamlit Community Cloud (an internal server, a different cloud
platform), a Dockerfile is straightforward, since a Streamlit app is just a Python process
listening on a port:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t my-dashboard .
docker run -p 8501:8501 my-dashboard
```

Once containerized, the same options discussed for a Python API
([Python API Backend, Deployment, §5](../02-python-api-backend/04-deployment.md#5-cloud-platform-options))
apply here too — a managed container platform (Cloud Run, ECS/Fargate) is usually the
simplest way to run it continuously without managing a server yourself.

## 3. Secrets management

Configuration values that shouldn't be committed to source control (API keys, database
credentials) are handled via `st.secrets`, backed by a `.streamlit/secrets.toml` file (kept
out of version control) locally, or the hosting platform's own secrets UI in production:

```toml
# .streamlit/secrets.toml (never committed)
[database]
url = "postgresql://..."
```

```python
db_url = st.secrets["database"]["url"]
```

This is the Streamlit-specific mechanism for the same "configuration over hardcoding"
principle discussed throughout this series — see
[the architecture overview, §2.7](../00-architecture-overview.md#27-configuration-over-hardcoding).

## 4. Core tools summary

| Tool | Used for |
|---|---|
| **Streamlit Community Cloud** | zero-infrastructure hosting directly from a GitHub repository |
| **Docker** | packaging the app for deployment anywhere else |
| **`st.secrets`** | managing credentials/configuration without committing them to source control |

## See also

- [Streamlit index](00-index.md)
- [Testing](03-testing.md) — verifying the app before it's deployed
- [Architecture Overview, §11](../00-architecture-overview.md#11-deployment-topology--how-these-layers-typically-get-deployed-together)
