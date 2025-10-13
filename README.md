# Minecraft RCON Server

## TL;DR

Allows for easy administration of a Minecraft server over network

## Features

- Web UI for seamless management for admins
- API for integrations (Discord bot, for example)
- Fast setup

## Implementation Details

### Tech Stack

#### Backend (backend/)

- Python
- Asyncio
- FastAPI
- SQLite
- uv
- ruff

The RCON client is heavily inspired by [this async RCON client](https://github.com/Iapetus-11/aio-mc-rcon) by [Iapetus-11](https://github.com/Iapetus-11).

#### Frontend (frontend/)

- TypeScript
- JavaScript
- React
- Tailwind CSS
- ShadCN
- Radix
- Lucide
- Prettier
- ESLint
- Vite

### Architecture Diagram

Crucially, note that for deploying this server, TLS is handled by a reverse proxy like Nginx or Apache.

- TODO: Need to add this from Excalidraw
