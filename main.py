from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
import random
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- DATABASE & ROLES ---
users_db = {
    "admin": {
        "password": "123", 
        "role": "admin", 
        "name": "System Admin",
        "desc": "Full Hardware Access"
    },
    "jane": {
        "password": "123", 
        "role": "expert", 
        "name": "Jane Doe",
        "desc": "Agronomist / Analyst"
    },
    "john": {
        "password": "123", 
        "role": "farmer", 
        "name": "Farmer John",
        "desc": "Field Operations"
    }
}

class LoginRequest(BaseModel):
    username: str
    password: str

# --- PAGE ROUTES ---

@app.get("/")
async def login_page(request: Request):
    """Serves the standalone Login Page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard")
async def dashboard_page(request: Request):
    """Serves the Dashboard (Authentication check is frontend for prototype)"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# --- API ROUTES ---

@app.post("/api/login")
async def login(data: LoginRequest):
    user = users_db.get(data.username)
    if not user or user["password"] != data.password:
        return JSONResponse(content={"success": False, "message": "Invalid Credentials"}, status_code=401)
    
    # Send back the role so the frontend knows how to render the dashboard
    return {
        "success": True, 
        "role": user["role"], 
        "name": user["name"], 
        "redirect": "/dashboard"
    }

@app.get("/api/live-data")
async def live_data():
    """Simulates the Real-time AI Library"""
    # Randomly fluctuate confidence
    return {
        "status": random.choice(["Healthy", "Healthy", "Healthy", "Rust Fungus"]),
        "confidence": random.uniform(0.75, 0.99),
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }