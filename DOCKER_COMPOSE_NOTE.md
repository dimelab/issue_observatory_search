# Docker Compose Command Note

## Important: Docker Compose v1 vs v2

The documentation may reference both command formats:

### Docker Compose v1 (deprecated)
```bash
docker-compose up -d
docker-compose ps
docker-compose logs
```

### Docker Compose v2 (current)
```bash
docker compose up -d
docker compose ps
docker compose logs
```

## Which One Should You Use?

**Use whichever works on your system!** The setup script (`scripts/setup_test_db.sh`) automatically detects which version you have.

### Check Your Version

```bash
# Check if you have v1 (hyphenated)
docker-compose --version

# Check if you have v2 (space)
docker compose version
```

### Quick Reference

| v1 Command | v2 Command |
|------------|------------|
| `docker-compose up` | `docker compose up` |
| `docker-compose down` | `docker compose down` |
| `docker-compose ps` | `docker compose ps` |
| `docker-compose logs` | `docker compose logs` |
| `docker-compose exec` | `docker compose exec` |
| `docker-compose restart` | `docker compose restart` |

## Both Work in Documentation

When you see `docker-compose` in the docs, you can substitute `docker compose` if you're using v2.

Example:
```bash
# Documentation says:
docker-compose up -d postgres

# If you have v2, use:
docker compose up -d postgres
```

## Setup Script Handles This

The test database setup script automatically detects and uses the correct command:

```bash
bash scripts/setup_test_db.sh
# Will output: "ℹ️  Using: docker compose" or "ℹ️  Using: docker-compose"
```

## Installing Docker Compose v2

If you have v1 and want to upgrade to v2:

### Linux
```bash
# Remove v1
sudo rm /usr/local/bin/docker-compose

# v2 comes with Docker Desktop or install plugin
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

### macOS
```bash
# Usually comes with Docker Desktop
# Or via Homebrew:
brew install docker-compose
```

### Windows
Docker Desktop for Windows includes v2 by default.

## Both Versions Work

**The good news:** Both versions work identically for all commands in this project. The only difference is the hyphen vs space.

## Summary

- ✅ **v1**: `docker-compose` (with hyphen)
- ✅ **v2**: `docker compose` (with space)
- ✅ **Both work!** Use whichever you have installed
- ✅ **Setup script** detects and uses the correct one automatically

Throughout the documentation, when you see `docker-compose`, just use whatever works on your system!
