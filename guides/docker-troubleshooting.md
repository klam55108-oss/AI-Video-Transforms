# Docker Daemon Troubleshooting Guide

This guide addresses common issues when connecting to the Docker daemon, specifically the "Cannot connect to the Docker daemon at unix:///var/run/docker.sock" error.

## Symptom

When running Docker commands (e.g., `docker ps`), you receive the following error:

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

## Troubleshooting Steps

Follow these steps in order to diagnose and fix the issue.

### 1. Check if Docker is Running

First, verify if the Docker service is actually active.

```bash
sudo systemctl status docker
```

**If it's not running:**
Start the service:
```bash
sudo systemctl start docker
```

**If it is running:**
Proceed to the next step.

### 2. Check User Permissions

Ensure your user is in the `docker` group.

```bash
groups
```

You should see `docker` in the list.

**If `docker` is missing:**
Add your user to the group and log out/in (or use `newgrp docker` for the current session):
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Check for Stale Docker Socket

If the service is running and permissions are correct, the socket file might be stale or unresponsive.

Check the timestamp of the socket file:
```bash
ls -l /var/run/docker.sock
```

If the date is old (e.g., from a previous boot or days ago) despite the service running, the socket is stale.

### 4. The Fix: Restart the Socket

Restarting the Docker service alone might not always fix a stale socket. You should restart the socket unit specifically.

```bash
# Restart the docker socket
sudo systemctl restart docker.socket

# Optionally, restart the service as well
sudo systemctl restart docker
```

Verify the fix:
```bash
docker ps
```

## Summary of Commands

If you encounter this issue, run this sequence:

```bash
# 1. Check status
sudo systemctl status docker

# 2. Restart socket (most likely fix for "Cannot connect" if daemon is up)
sudo systemctl restart docker.socket

# 3. Verify
docker ps
```
