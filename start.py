import subprocess
import sys
import os
import signal
import time
import json
import argparse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from passlib.hash import bcrypt
import psutil

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./probe.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def parse_args():
    parser = argparse.ArgumentParser(description='探针服务启动脚本')
    parser.add_argument('-p', '--params', type=str, help='配置参数，格式：web端口,ws端口')
    return parser.parse_args()

def get_db_credentials():
    try:
        if os.path.exists("probe.db"):
            db = SessionLocal()
            user = db.query(User).first()
            db.close()
            if user:
                return {"username": user.username, "password": user.password}
    except Exception as e:
        print(f"读取数据库失败: {e}")
    return {"username": "admin", "password": bcrypt.hash("admin")}

# 数据模型
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  # 存储加密后的密码

def get_user_input():
    print("\n=== 探针服务配置 ===")
    
    # 获取Web服务端口
    while True:
        web_port = input("请输入Web服务端口 (默认60000): ").strip()
        if not web_port:
            web_port = "60000"
        try:
            web_port = int(web_port)
            if 1 <= web_port <= 65535:
                break
            print("端口号必须在1-65535之间")
        except ValueError:
            print("请输入有效的端口号")
    
    # 获取WebSocket服务端口
    while True:
        ws_port = input("请输入WebSocket服务端口 (默认60001): ").strip()
        if not ws_port:
            ws_port = "60001"
        try:
            ws_port = int(ws_port)
            if 1 <= ws_port <= 65535:
                if ws_port != web_port:
                    break
                print("WebSocket端口不能与Web端口相同")
            else:
                print("端口号必须在1-65535之间")
        except ValueError:
            print("请输入有效的端口号")
    
    # 从数据库获取用户名和密码
    credentials = get_db_credentials()
    
    return {
        "web_port": web_port,
        "ws_port": ws_port,
        "username": credentials["username"],
        "password": credentials["password"]
    }

def parse_params(params_str):
    try:
        # 分割参数字符串
        params = params_str.split(',')
        if len(params) != 2:
            print("错误：参数数量不正确，需要2个参数：web端口,ws端口")
            sys.exit(1)
        
        # 解析端口号
        web_port = int(params[0])
        ws_port = int(params[1])
        
        # 验证端口号
        if not (1 <= web_port <= 65535 and 1 <= ws_port <= 65535):
            print("错误：端口号必须在1-65535之间")
            sys.exit(1)
        if web_port == ws_port:
            print("错误：Web端口和WebSocket端口不能相同")
            sys.exit(1)
        
        # 从数据库获取用户名和密码
        credentials = get_db_credentials()
        
        return {
            "web_port": web_port,
            "ws_port": ws_port,
            "username": credentials["username"],
            "password": credentials["password"]
        }
    except ValueError:
        print("错误：端口号必须是数字")
        sys.exit(1)
    except Exception as e:
        print(f"错误：参数解析失败 - {str(e)}")
        sys.exit(1)

def cleanup_processes(main_process, ws_process, config_file, config):
    try:
        # 获取所有子进程
        def get_child_processes(pid):
            children = []
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            return children

        # 终止主进程及其子进程
        if main_process:
            main_pid = main_process.pid
            for child in get_child_processes(main_pid):
                try:
                    child.terminate()
                except:
                    pass
            try:
                main_process.terminate()
            except:
                pass

        # 终止WebSocket进程及其子进程
        if ws_process:
            ws_pid = ws_process.pid
            for child in get_child_processes(ws_pid):
                try:
                    child.terminate()
                except:
                    pass
            try:
                ws_process.terminate()
            except:
                pass

        # 等待进程结束
        if main_process:
            try:
                main_process.wait(timeout=5)
            except:
                try:
                    os.kill(main_pid, signal.SIGKILL)
                except:
                    pass

        if ws_process:
            try:
                ws_process.wait(timeout=5)
            except:
                try:
                    os.kill(ws_pid, signal.SIGKILL)
                except:
                    pass

        # 删除临时配置文件
        try:
            os.remove(config_file)
        except:
            pass

        # 检查端口占用
        def check_port(port):
            for conn in psutil.net_connections():
                if conn.laddr.port == port:
                    try:
                        psutil.Process(conn.pid).terminate()
                    except:
                        pass

        # 检查并清理可能被占用的端口
        check_port(config['web_port'])
        check_port(config['ws_port'])

        print("所有服务已停止")
    except Exception as e:
        print(f"清理进程时发生错误: {e}")

def run_services():
    args = parse_args()
    if args.params:
        config = parse_params(args.params)
    else:
        print("未提供命令行参数，请手动输入配置信息")
        config = get_user_input()
    config_file = "temp_config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 检查端口是否被占用
    def is_port_in_use(port):
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                return True
        return False

    # 如果端口被占用，先尝试终止占用进程
    if is_port_in_use(config['web_port']):
        print(f"端口 {config['web_port']} 已被占用，尝试释放...")
        for conn in psutil.net_connections():
            if conn.laddr.port == config['web_port']:
                try:
                    psutil.Process(conn.pid).terminate()
                except:
                    pass
        time.sleep(1)  # 等待端口释放

    if is_port_in_use(config['ws_port']):
        print(f"端口 {config['ws_port']} 已被占用，尝试释放...")
        for conn in psutil.net_connections():
            if conn.laddr.port == config['ws_port']:
                try:
                    psutil.Process(conn.pid).terminate()
                except:
                    pass
        time.sleep(1)  # 等待端口释放

    main_process = subprocess.Popen([sys.executable, 'web.py', '--config', config_file],
                                cwd=current_dir)
    ws_process = subprocess.Popen([sys.executable, 'ws_server.py', '--port', str(config['ws_port'])],
                              cwd=current_dir)
    print("\n服务已启动:")
    print(f"- Web服务运行在 http://localhost:{config['web_port']}")
    print(f"- WebSocket服务运行在 ws://localhost:{config['ws_port']}")
    print(f"- 管理员账号: {config['username']}")
    print(f"- 管理员密码(加密): {config['password']}")
    print("\n按 Ctrl+C 停止所有服务...")
    try:
        while True:
            # 只检查进程是否还在运行，不再读取输出
            if main_process.poll() is not None or ws_process.poll() is not None:
                if main_process.poll() is not None:
                    print("Web(FastAPI) 服务异常退出！")
                if ws_process.poll() is not None:
                    print("WebSocket 服务异常退出！")
                print("服务异常退出，正在关闭所有子进程...")
                cleanup_processes(main_process, ws_process, config_file, config)
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        cleanup_processes(main_process, ws_process, config_file, config)
    except Exception as e:
        print(f"主程序异常: {e}")
        cleanup_processes(main_process, ws_process, config_file, config)

if __name__ == "__main__":
    run_services() 