from __future__ import annotations
import os, logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from ..security.secrets import ConnectFlow
from ..config.settings import store_from_env
from ..clients.woocommerce_client import WooClient
from ..models.errors import AuthError, ConnectorError, ValidationError

router=APIRouter()
log=logging.getLogger("woo_connector.api")

_flow=None
def flow():
    global _flow
    if _flow is None:
        allow=os.environ.get("ALLOW_INSECURE_LOCAL","").lower() in ("1","true","yes")
        async def verify(store_url:str,key:str,secret:str):
            async with WooClient(store_url,key,secret,max_retries=1,allow_insecure=allow) as client:
                await client.get("products",{"per_page":1})
                
        _flow=ConnectFlow(store_from_env(),public_base_url=os.environ.get("PUBLIC_BASE_URL","http://localhost:8787"),
                          allow_insecure=allow,verifier=verify)
    return _flow

@router.get("/connect")
async def connect(store:str, merchant_id:str):
    try: 
        return RedirectResponse(flow().start(store,merchant_id),status_code=302)
    except ValidationError as exc: 
        raise HTTPException(status_code=400,detail=exc.message) from None

@router.post("/callback")
async def callback(request:Request):
    try: payload=await request.json()
    except Exception: 
        return JSONResponse({"error":"invalid_json"},status_code=400)
    try: 
        creds=await flow().complete(payload)
    except AuthError: 
        return JSONResponse({"error":"rejected"},status_code=403)
    
    except ConnectorError as exc: 
        return JSONResponse({"error":exc.code},status_code=400)
    
    log.info("merchant_connected",extra={"merchant_id":creds.merchant_id})
    return JSONResponse({"ok":True})

@router.get("/connected",response_class=HTMLResponse)
async def connected(): 
    return "<h1>Store connected</h1><p>You can close this tab and return to your agent.</p>"
