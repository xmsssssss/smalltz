from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import json
import asyncio
from datetime import datetime
import uvicorn
from typing import Dict, List
from starlette.middleware.sessions import SessionMiddleware
import os
from passlib.hash import bcrypt

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./probe.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 数据模型
class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="{}")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  # 存储加密后的密码

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 初始化账号密码
def init_admin_user():
    db = SessionLocal()
    if db.query(User).count() == 0:
        admin_user = User(username=config["username"], password=bcrypt.hash(config["password"]))
        db.add(admin_user)
        db.commit()
    db.close()

# 默认配置
config = {
    "web_port": 60000,
    "ws_port": 60001,
    "username": "admin",
    "password": "admin"
}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='配置文件路径')
    args = parser.parse_args()
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            exit(1)
    # 重新初始化账号（防止config未被正确覆盖）
    init_admin_user()
    uvicorn.run("web:app", host="0.0.0.0", port=config["web_port"], reload=True)
else:
    # 被import时只用默认config，不做参数解析
    pass

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
# 存储活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}

app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")

# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            # 更新客户端状态
            db = SessionLocal()
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client.status = data
                client.last_seen = datetime.utcnow()
                db.commit()
            db.close()
            print(f"收到客户端 {client_id} 状态: {data}")
    except WebSocketDisconnect:
        del active_connections[client_id]

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    clients = db.query(Client).filter(Client.is_active == True).all()
    is_logged_in = request.session.get("user") == config["username"]
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "clients": clients, "is_logged_in": is_logged_in}
    )

@app.get("/api/clients")
async def get_clients(db: Session = Depends(get_db)):
    clients = db.query(Client).all()
    return clients

@app.post("/api/clients/{client_id}/toggle")
async def toggle_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.client_id == client_id).first()
    if client:
        client.is_active = not client.is_active
        db.commit()
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Client not found")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.client_id == client_id).first()
    if client:
        db.delete(client)
        db.commit()
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Client not found")

# 登录页
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if user and bcrypt.verify(password, user.password):
        response = RedirectResponse(url="/admin", status_code=302)
        request.session["user"] = username
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "用户名或密码错误"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

def require_login(request: Request):
    if request.session.get("user") != config["username"]:
        return False
    return True

# 管理面板
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    if not require_login(request):
        return RedirectResponse(url="/login", status_code=302)
    clients = db.query(Client).all()
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "clients": clients}
    )

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse("reset_password.html", {"request": request, "error": None})

@app.post("/reset-password", response_class=HTMLResponse)
async def reset_password(
    request: Request,
    old_username: str = Form(...),
    old_password: str = Form(...),
    new_username: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    # 验证原账号密码
    user = db.query(User).filter(User.username == old_username).first()
    if not user or not bcrypt.verify(old_password, user.password):
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "error": "原账号或密码错误"}
        )
    
    # 更新账号密码
    user.username = new_username
    user.password = bcrypt.hash(new_password)
    db.commit()
    
    # 重定向到登录页
    return RedirectResponse(url="/login", status_code=302) 