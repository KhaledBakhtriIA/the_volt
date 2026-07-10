# Docker Setup Guide for Volt Data API

## Quick Start

### 1. Prerequisites
- Docker Engine ≥ 20.10
- Docker Compose ≥ 1.29
- (Optional) 4GB+ RAM, 2+ CPU cores for optimal performance

### 2. Build and Run

```bash
# Clone or navigate to the project directory
cd the_volt_system

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys and settings

# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f volt-data-api

# Verify it's running
curl http://localhost:8000/health
```

### 3. Configuration

All settings are controlled via environment variables in `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_API_HOST` | 0.0.0.0 | Bind address (0.0.0.0 for Docker) |
| `DATA_API_PORT` | 8000 | API port |
| `DATA_API_INTERVAL` | 1d | Data collection interval |
| `DATA_API_LOOKBACK_DAYS` | 365 | Historical lookback period |
| `DATA_API_BROWSER_ENABLED` | false | Enable browser automation |
| `DATA_API_REDDIT_ENABLED` | false | Enable Reddit integration |
| `DATA_API_MACRO_ENABLED` | false | Enable FRED macro data |

See `.env.example` for all available options.

### 4. API Endpoints

Once running, access the API at `http://localhost:8000`:

- **Health Check**: `GET /health`
- **API Documentation**: `GET /docs` (Swagger UI)
- **Market Data**: `POST /collect/market`
- **News**: `POST /collect/news`
- **Full Collection**: `POST /collect/full`
- **Latest Dataset**: `GET /datasets/latest`

### 5. Data Persistence

Data directories are mounted as volumes to prevent loss on container restart:
- `data_api/data/raw` → Raw collected data
- `data_api/data/processed` → Processed datasets
- `data_api/logs` → Application logs

### 6. Development Mode

For development, mount the source code:

```bash
# Edit docker-compose.yml and add:
volumes:
  - .:/app  # Live code reload
  - ./data_api/data:/app/data_api/data
  - ./data_api/logs:/app/data_api/logs
```

Then rebuild and restart:
```bash
docker-compose up --build
```

### 7. Stopping and Cleanup

```bash
# Stop the service
docker-compose down

# Remove all data (WARNING: Data loss!)
docker-compose down -v

# View logs after shutdown
docker-compose logs volt-data-api
```

### 8. Troubleshooting

**Port Already in Use**
```bash
# Use a different port
DATA_API_PORT=8001 docker-compose up -d
# Or edit .env and set DATA_API_PORT=8001
```

**Container Won't Start**
```bash
# Check detailed logs
docker-compose logs volt-data-api

# Rebuild from scratch
docker-compose build --no-cache
```

**Out of Memory**
Ensure Docker has at least 4GB allocated (Docker Desktop settings).

**Permission Denied (Linux)**
```bash
sudo usermod -aG docker $USER
# Restart Docker daemon or logout/login
```

### 9. Production Deployment

For production environments:

1. **Use environment-specific .env files**:
   ```bash
   cp .env.example .env.production
   # Configure API keys
   ```

2. **Enable security best practices**:
   - Use read-only volumes where possible
   - Set resource limits in docker-compose.yml
   - Use a reverse proxy (nginx/traefik) in front

3. **Monitor and logs**:
   - Mount logs to persistent storage
   - Use Docker logging drivers (ELK, Splunk, etc.)
   - Set up health check alerts

4. **Scaling** (optional, requires orchestration):
   - For Kubernetes: Adapt docker-compose.yml to Helm charts
   - For Swarm: Use `docker stack deploy`

### 10. Common Commands

```bash
# View running services
docker-compose ps

# Rebuild without cache
docker-compose build --no-cache

# Run a one-off command in container
docker-compose exec volt-data-api python -m pytest

# View detailed logs (last 100 lines)
docker-compose logs --tail=100 volt-data-api

# Restart service
docker-compose restart volt-data-api

# Update and restart
docker-compose pull && docker-compose up -d --force-recreate
```

### 11. Integration with CI/CD

Push to a registry:
```bash
# Build and tag
docker build -t myregistry/volt-data-api:1.0 .

# Push
docker push myregistry/volt-data-api:1.0

# Use in docker-compose.yml
image: myregistry/volt-data-api:1.0
```

---

**For more help**: Check logs with `docker-compose logs` or review the Dockerfile for details on the build process.
