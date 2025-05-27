import subprocess
import sys
import os
import signal
import time
import json
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='探针服务启动脚本')
    parser.add_argument('-p', '--params', type=str, help='配置参数，格式：web端口,ws端口,用户名,密码')
    return parser.parse_args()

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
    
    # 获取管理员用户名
    username = input("请输入管理员用户名 (默认admin): ").strip()
    if not username:
        username = "admin"
    
    # 获取管理员密码
    password = input("请输入管理员密码 (默认admin): ").strip()
    if not password:
        password = "admin"
    
    return {
        "web_port": web_port,
        "ws_port": ws_port,
        "username": username,
        "password": password
    }

def parse_params(params_str):
    try:
        # 分割参数字符串
        params = params_str.split(',')
        if len(params) != 4:
            print("错误：参数数量不正确，需要4个参数：web端口,ws端口,用户名,密码")
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
        
        return {
            "web_port": web_port,
            "ws_port": ws_port,
            "username": params[2],
            "password": params[3]
        }
    except ValueError:
        print("错误：端口号必须是数字")
        sys.exit(1)
    except Exception as e:
        print(f"错误：参数解析失败 - {str(e)}")
        sys.exit(1)

def cleanup_processes(main_process, ws_process, config_file):
    # 停止所有进程
    if main_process and main_process.poll() is None:
        main_process.terminate()
    if ws_process and ws_process.poll() is None:
        ws_process.terminate()
    # 等待进程结束
    if main_process:
        try:
            main_process.wait(timeout=5)
        except Exception:
            pass
    if ws_process:
        try:
            ws_process.wait(timeout=5)
        except Exception:
            pass
    # 删除临时配置文件
    try:
        os.remove(config_file)
    except:
        pass
    print("所有服务已停止")

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
    main_process = subprocess.Popen([sys.executable, 'web.py', '--config', config_file],
                                  cwd=current_dir,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True)
    ws_process = subprocess.Popen([sys.executable, 'ws_server.py', '--port', str(config['ws_port'])],
                                cwd=current_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
    print("\n服务已启动:")
    print(f"- Web服务运行在 http://localhost:{config['web_port']}")
    print(f"- WebSocket服务运行在 ws://localhost:{config['ws_port']}")
    print(f"- 管理员账号: {config['username']}")
    print(f"- 管理员密码: {config['password']}")
    print("\n按 Ctrl+C 停止所有服务...")
    try:
        while True:
            main_output = main_process.stdout.readline()
            if main_output:
                print(f"[Web] {main_output.strip()}")
            ws_output = ws_process.stdout.readline()
            if ws_output:
                print(f"[WebSocket] {ws_output.strip()}")
            # 检查进程是否还在运行
            if main_process.poll() is not None or ws_process.poll() is not None:
                if main_process.poll() is not None:
                    print("Web(FastAPI) 服务异常退出！")
                    err = main_process.stderr.read()
                    if err:
                        print("[Web Error]", err)
                if ws_process.poll() is not None:
                    print("WebSocket 服务异常退出！")
                    err = ws_process.stderr.read()
                    if err:
                        print("[WebSocket Error]", err)
                print("服务异常退出，正在关闭所有子进程...")
                cleanup_processes(main_process, ws_process, config_file)
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        cleanup_processes(main_process, ws_process, config_file)
    except Exception as e:
        print(f"主程序异常: {e}")
        cleanup_processes(main_process, ws_process, config_file)

if __name__ == "__main__":
    run_services() 