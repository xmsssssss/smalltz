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
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
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
        admin_user = User(username="admin", password=bcrypt.hash("admin"))
        db.add(admin_user)
        db.commit()
    db.close()

# 默认配置
config = {
    "web_port": 60000,
    "ws_port": 60001,
    "username": "",
    "password": ""
}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, help='配置文件路径')
    args = parser.parse_args()
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if "web_port" in user_config:
                    config["web_port"] = user_config["web_port"]
                if "ws_port" in user_config:
                    config["ws_port"] = user_config["ws_port"]
                if "username" in user_config:
                    config["username"] = user_config["username"]
                    config["password"] = user_config["password"]
        except Exception as e:
            print(f"读取配置文件失败: {e}")
            exit(1)
    # 初始化账号（使用默认的admin/admin）
    init_admin_user()
    uvicorn.run("web:app", host="0.0.0.0", port=config["web_port"])
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
    except Exception as e:
        print(f"数据库操作错误: {e}")
        db.rollback()
        raise
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
            try:
                client = db.query(Client).filter(Client.client_id == client_id).first()
                if client:
                    # 只有活跃的客户端才更新状态
                    if client.is_active:
                        client.status = data
                        client.last_seen = datetime.utcnow()
                        db.commit()
                    print(f"收到客户端 {client_id} 状态: {data}")
                else:
                    print(f"收到未知客户端 {client_id} 状态: {data}，未找到对应记录")
            except Exception as e:
                print(f"更新客户端状态失败: {e}")
                db.rollback()
            finally:
                db.close()
    except WebSocketDisconnect:
        del active_connections[client_id]
    except Exception as e:
        print(f"WebSocket连接异常: {e}")
        if client_id in active_connections:
            del active_connections[client_id]

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    clients = db.query(Client).all() # 返回所有客户端，以便前端能够显示隐藏的客户端
    username = request.session.get("user")
    is_logged_in = False
    if username:
        user = db.query(User).filter(User.username == username).first()
        is_logged_in = user is not None
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "clients": clients, "is_logged_in": is_logged_in}
    )

@app.get("/api/clients")
async def get_clients(db: Session = Depends(get_db)):
    clients_from_db = db.query(Client).all()
    # 为前端准备数据：对于非活跃客户端，清空其status字段以停止前端显示实时数据
    clients_for_frontend = []
    for client in clients_from_db:
        if not client.is_active:
            # 创建一个客户端的副本，修改其status字段，避免影响数据库中原始对象
            client_data = client.__dict__.copy()
            if "_sa_instance_state" in client_data: # 移除SQLAlchemy内部状态对象
                del client_data["_sa_instance_state"]
            client_data["status"] = "{}" # 将status设为空JSON字符串
            clients_for_frontend.append(client_data)
        else:
            # 活跃客户端直接使用原始数据
            client_data = client.__dict__.copy()
            if "_sa_instance_state" in client_data: # 移除SQLAlchemy内部状态对象
                del client_data["_sa_instance_state"]
            clients_for_frontend.append(client_data)
    return clients_for_frontend

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

def require_login(request: Request, db: Session = Depends(get_db)):
    username = request.session.get("user")
    if not username:
        return False
    user = db.query(User).filter(User.username == username).first()
    return user is not None

# 管理面板
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    if not require_login(request, db):
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
    
    # 更新config中的用户名和密码
    config["username"] = new_username
    config["password"] = bcrypt.hash(new_password)
    
    # 重定向到登录页
    return RedirectResponse(url="/login", status_code=302) 