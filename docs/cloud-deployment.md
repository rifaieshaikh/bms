# Cloud Deployment Guide

VayBooks-BMS supports cloud hosting alongside the desktop installer. Deploy only the `bms/` directory.

## Streamlit Community Cloud

1. Connect your GitHub repository
2. Set main file path: `bms/app.py`
3. Add secrets in the Streamlit Cloud dashboard:

```toml
MONGODB_URI = "mongodb+srv://..."
MONGODB_DATABASE = "zahcci_customization"
```

4. Deploy — migrations run automatically on startup

## Docker (AWS ECS, App Runner, Azure, etc.)

```bash
cd bms
docker build -t vaybooks-bms .
docker run -p 8501:8501 \
  -e MONGODB_URI="mongodb+srv://..." \
  -e MONGODB_DATABASE="zahcci_customization" \
  vaybooks-bms
```

## AWS App Runner

1. Push Docker image to ECR
2. Create App Runner service from the image
3. Set environment variables: `MONGODB_URI`, `MONGODB_DATABASE`
4. Expose port 8501

## Azure App Service

1. Deploy the Docker container or use Python 3.11 runtime
2. Set Application Settings for `MONGODB_URI` and `MONGODB_DATABASE`
3. Startup command: `streamlit run app.py --server.headless=true --server.port=8501`

## Runtime Mode Detection

| Variable | Effect |
|----------|--------|
| Not set | Cloud mode — uses secrets/env |
| `VAYBOOKS_DATA_DIR` set | Desktop mode — uses ProgramData config |

Cloud deployments should **not** set `VAYBOOKS_DATA_DIR`.

## Features by Mode

| Feature | Cloud | Desktop |
|---------|-------|---------|
| Business modules | Yes | Yes |
| Migrations | Yes | Yes |
| Version display | Yes | Yes |
| Export / Backup | Yes | Yes |
| System Settings UI | No | Yes |
| In-app updater | No | Yes |
| Log file viewer | No | Yes |

## CI/CD

Cloud deploys use the same `bms/` codebase. Tag releases with `v*.*.*` to trigger the release workflow for desktop installers. Cloud hosts can deploy from the same tag independently.
