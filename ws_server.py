import asyncio
import websockets
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from web import Client, Base, SQLALCHEMY_DATABASE_URL
import argparse

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def handler(websocket, path):
    # 客户端ID从路径获取，例如 ws://host:8001/ws/{client_id}
    if not path.startswith('/ws/'):
        await websocket.close()
        return
    client_id = path.split('/ws/')[-1]
    db = SessionLocal()
    try:
        # 查找或创建客户端
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if not client:
            client = Client(client_id=client_id, name=client_id, is_active=True)
            db.add(client)
            db.commit()
        while True:
            data = await websocket.recv()
            client.status = data
            client.last_seen = datetime.utcnow()
            db.commit()
            # print(f"收到客户端 {client_id} 状态: {data}")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=60001, help='WebSocket服务端口')
    args = parser.parse_args()
    start_server = websockets.serve(handler, "0.0.0.0", args.port)
    print(f"WebSocket服务已启动，监听端口{args.port}...")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever() 