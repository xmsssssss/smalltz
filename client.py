import asyncio
import websockets
import json
import platform
import psutil
import uuid
import time
import argparse
import os
import socket
import sys
import requests

# 存储上一次的网络数据
last_net_io = None
last_net_time = None

def get_main_disk():
    sys = platform.system()
    if sys == 'Windows':
        return 'C:\\'
    else:
        return '/'

def get_ip_mac():
    ip = None
    mac = None
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    ip = addr.address
                if hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK:
                    mac = addr.address
                elif hasattr(socket, 'AF_PACKET') and addr.family == socket.AF_PACKET:
                    mac = addr.address
            if ip and mac:
                break
    except Exception:
        pass
    return ip, mac

def get_ip_region():
    try:
        response = requests.get('http://ip-api.com/json/?fields=countryCode,country', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('countryCode', ''), data.get('country', '')
    except:
        pass
    return '', ''

def get_status():
    global last_net_io, last_net_time
    disk = get_main_disk()
    net = psutil.net_io_counters()
    ip, mac = get_ip_mac()
    memory = psutil.virtual_memory()
    disk_usage = psutil.disk_usage(disk) if os.path.exists(disk) else None
    
    # 计算网络速度
    current_time = time.time()
    upload_speed = 0
    download_speed = 0
    
    if last_net_io is not None and last_net_time is not None:
        time_diff = current_time - last_net_time
        if time_diff > 0:
            upload_speed = (net.bytes_sent - last_net_io.bytes_sent) / time_diff
            download_speed = (net.bytes_recv - last_net_io.bytes_recv) / time_diff
    
    # 更新上一次的数据
    last_net_io = net
    last_net_time = current_time
    
    return {
        "system": {
            "platform": platform.platform(),
            "os": platform.system(),
            "hostname": platform.node(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": memory.percent,
            "memory_total": f"{memory.total / (1024**3):.2f}GiB",
            "disk_usage": disk_usage.percent if disk_usage else None,
            "disk_total": f"{disk_usage.total / (1024**3):.0f}GiB" if disk_usage else None,
            "boot_time": psutil.boot_time(),
            "ip": ip,
            "mac": mac,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "upload_speed": f"{upload_speed:.2f}",
            "download_speed": f"{download_speed:.2f}"
        },
        "timestamp": time.time()
    }

async def send_status(uri, client_id, interval):
    # 获取IP地区信息
    country_code, country_name = get_ip_region()
    print(f"[INFO] 服务器地区: {country_name} ({country_code})")
    
    while True:
        try:
            async with websockets.connect(f"{uri}/ws/{client_id}") as websocket:
                print(f"[INFO] 已连接到 {uri}/ws/{client_id}")
                while True:
                    status = get_status()
                    # 添加地区信息
                    status["system"]["country_code"] = country_code
                    status["system"]["country_name"] = country_name
                    await websocket.send(json.dumps(status))
                    print(f"[SEND] {status}")
                    await asyncio.sleep(interval)
        except Exception as e:
            print(f"[ERROR] 连接失败或中断: {e}，3秒后重试...")
            await asyncio.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="探针客户端示例")
    parser.add_argument(
        '-p', '--params',
        type=str,
        required=True,
        help='客户端配置参数，格式：服务器地址:端口,客户端名称[,间隔(秒)]'
    )
    args = parser.parse_args()
    try:
        # 解析参数字符串
        params = args.params.split(',')
        if len(params) < 2:
            print("错误：参数不足，至少需要：服务器地址:端口,客户端名称")
            sys.exit(1)
        server_address = params[0].strip()
        client_id = params[1].strip()
        interval = 5 # Default interval
        if len(params) > 2:
            try:
                interval = int(params[2].strip())
            except ValueError:
                print("错误：间隔时间必须是整数")
                sys.exit(1)
        # 构建 WebSocket URI
        # 假设服务器地址已经包含了 ws:// 或 wss:// 前缀
        # 如果需要更严格的验证或处理，可以再细化
        if not server_address.startswith("ws://") and not server_address.startswith("wss://"):
             # 如果没有协议头，默认使用 ws://
             uri = f"ws://{server_address}"
        else:
             uri = server_address
        print(f"[INFO] 启动探针客户端: server={uri}, client_id={client_id}, interval={interval}s")
        asyncio.run(send_status(uri, client_id, interval))
    except Exception as e:
        print(f"启动错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 