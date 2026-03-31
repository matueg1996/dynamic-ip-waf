"""
Punto de entrada principal de la aplicación FastAPI.
Configura los routers, la base de datos y los middlewares.
"""
from fastapi import FastAPI
from app.api.rutas import router
from app.api.slack import slack_router
from app.db.database import Base, engine
import app.db.esquemas

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gestor de IPs para WAF")

app.include_router(router)
app.include_router(slack_router, prefix="/slack")