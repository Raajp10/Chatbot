from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.query import router as query_router
from app.config import ServiceUnavailableError

app = FastAPI(title="PNW Student Knowledge Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)


@app.exception_handler(ServiceUnavailableError)
def service_unavailable_handler(request: Request, exc: ServiceUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": str(exc)})
