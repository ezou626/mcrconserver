# Minecraft RCON Server

## TL;DR

Allows for easy administration of a Minecraft server over network, allowing for integrations with Discord bots, for example

## Features

- Authenticated HTTP routes for sending RCON commands
- Web UI for admins

## Implementation Details

### Tech Stack

#### Backend (backend/)

- Python
- Asyncio
- FastAPI
- SQLite
- uv
- ruff

The async RCON connection is heavily inspired by [this async RCON client](https://github.com/Iapetus-11/aio-mc-rcon) by [Iapetus-11](https://github.com/Iapetus-11). The main addition is that the SocketClient that communicates with the server is not designed to be used by itself. Rather, we run a worker with a queue and expose a synchronous send operation to put a job in the queue for the worker to handle. Then, the result can be awaited with a Future if desired. This is a bit more heavyweight, but works well for a web server where we may sometimes not want to wait for a result or deliver multiple commands in a short period of time. We can also natively allow for multiple workers to be spawned, using a few TCP connections to parallelize command execution.

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

Crucially, note that for deploying this server, SSL/TLS is handled by `uvicorn`'s in-built cert support or a reverse proxy like Nginx, Apache.

- TODO: Need to add this from Excalidraw
