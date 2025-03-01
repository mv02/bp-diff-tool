from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import database

app = FastAPI()


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, e: HTTPException):
    return JSONResponse({"message": e.detail}, e.status_code)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(database.router)
