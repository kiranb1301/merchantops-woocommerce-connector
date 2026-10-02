from __future__ import annotations
import contextlib
from fastapi import FastAPI
from starlette.routing import Mount
from .mcp.server import mcp
from .api.health import router as health_router
from .api.routes import router as connect_router
from .observability.logging import configure_logging


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    async with mcp.session_manager.run():
        yield


app=FastAPI(title="MerchantOps WooCommerce Connector", lifespan=lifespan)
app.include_router(health_router)
app.include_router(connect_router)
app.mount("/mcp", mcp.streamable_http_app(streamable_http_path="/"))


if __name__=="__main__":
    import uvicorn
    uvicorn.run("woo_connector.main:app",host="127.0.0.1",port=8000,reload=False)
