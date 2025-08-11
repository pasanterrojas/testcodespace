import os
from datetime import datetime
from typing import List

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, EmailStr, ValidationError
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from fastapi.responses import JSONResponse

import smtplib
from email.message import EmailMessage
import ssl

# ───────────────────── Configuración ──────────────────────
SMTP_SERVER   = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = os.getenv("SMTP_USER", "escaner.mfp17@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "mpcrstvcqfcdeqzu")  # Usa variables de entorno si podés

# ───────────────────── FastAPI ────────────────────────────
app = FastAPI(
    title="API de Reportes PDF por correo",
    description="Genera un PDF y lo envía por email."
)

env = Environment(loader=FileSystemLoader("templates"))

# ───────────────────── Modelo de entrada ──────────────────
class ReportData(BaseModel):
    tipo: str                                # "cooperativa" | "emprendimiento"
    correo: EmailStr                         # validación estricta de correo
    resumen: str
    temas: List[str]
    calificaciones: List[int]
    recomendaciones: List[str]

# ───────────────────── Utilidad de correo ─────────────────
def enviar_pdf(destinatario: str, pdf_bytes: bytes, asunto: str = "Reporte PDF"):
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    msg.set_content("Adjunto encontrarás el reporte en PDF generado automáticamente.\n\nSaludos.")

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename="reporte.pdf"
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls(context=context)
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)

# ───────────────────── Endpoint robusto ───────────────────
@app.post("/generar-pdf/")
async def generar_pdf_endpoint(request: Request, background_tasks: BackgroundTasks):
    try:
        # Cargar y validar el JSON recibido
        json_data = await request.json()
        data = ReportData(**json_data)

        # Validar que temas y calificaciones estén pareadas
        if len(data.temas) != len(data.calificaciones):
             print("⚠️ Advertencia: temas y calificaciones tienen diferente longitud.")

        # Renderiza HTML
        html = env.get_template("reporte_template.html").render(
            tipo=data.tipo,
            resumen=data.resumen,
            temas=data.temas,
            calificaciones=data.calificaciones,
            recomendaciones=data.recomendaciones,
            fecha=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )

        # Genera PDF
        pdf_bytes = HTML(string=html).write_pdf()

        # Envía en segundo plano
        background_tasks.add_task(
            enviar_pdf,
            destinatario=data.correo,
            pdf_bytes=pdf_bytes,
            asunto=f"Reporte de Madurez Digital – {data.tipo.title()}"
        )

        return {"success": True, "message": f"Reporte en camino a {data.correo}"}

    except ValidationError as ve:
        return JSONResponse(status_code=422, content={"validation_error": ve.errors()})

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

# ───────────────────── Endpoint raíz ──────────────────────
@app.get("/")
def read_root():
    return {"message": "API lista: POST /generar-pdf/ con tu JSON para recibir el reporte por email"}
