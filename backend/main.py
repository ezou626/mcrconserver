from fastapi import FastAPI
import logging
import uvicorn

app = FastAPI(title="MCRConServer API", version="0.0.1")

LOG = logging.getLogger(__name__)
LOG.info("API is starting up")
LOG.info(uvicorn.Config.asgi_version)


@app.get("/")
def read_root():
    return {"message": "Hello World!"}
