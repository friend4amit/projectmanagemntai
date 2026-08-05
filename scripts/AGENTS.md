# Scripts Agent Guidance

## Current state

The `scripts/` folder contains cross-platform start/stop scripts. The start scripts now pass `.env` into Docker with `--env-file .env` so the backend can use `OPENROUTER_API_KEY`.

## Responsibilities

- Add cross-platform scripts for starting and stopping the application.
- Support Windows PowerShell and Unix shell environments.
- Keep script logic minimal and clearly documented.

## Expected scripts

- `scripts/start.ps1` and `scripts/stop.ps1`
- `scripts/start.sh` and `scripts/stop.sh`

## Goals

- Part 2: provide simple scripted commands to build the Docker image and run the container.
- Make it easy for a developer to start the app locally without remembering Docker commands.
- Ensure stop scripts cleanly remove running containers.
- Ensure runtime env vars from `.env` are available inside the container.
