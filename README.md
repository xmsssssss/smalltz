# 小探针

针对哪吒部署太麻烦，ServerStatus需要编写配置文件，CTRL C+V抄了个小探针

BUG巨多 不对外开放

一个自用python小探针(python3.8+)

1.~~无传输安全措施~~ 登录带账号密码算么？

2.客户端上传无密码

3.ui垃圾

4.多端不兼容

...

---

# 服务端

打包下载，同目录直接执行以下代码：
>pip3 install -r requirements.txt

>nohup python3 start.py -p 60000,60001

"60000,60001"分别代表web端口、通信端口，web登录账号与密码默认都是`admin`，可在登录页面更改。


感觉上面有些乱啊，下面是一键安装代码，记得修改端口：

>sudo apt-get update && sudo apt-get install git python3 python3-pip && git clone https://github.com/xmsssssss/smalltz.git && cd smalltz && pip3 install -r requirements.txt && nohup python3 start.py -p `60000,60001` &


# 客户端

下载client.py
>pip3 install websockets
>
>pip3 install psutil 

>nohup python3 client.py -p ip:60001,银河超算,5

"ip:60001,银河超算,5"分别代表服务端ip、服务端ip通信端口、客户端名、定时上传间隔

感觉上面有些乱啊，下面是一键安装代码，记得修改ip、端口、名、间隔时间：

>wget https://raw.githubusercontent.com/xmsssssss/smalltz/refs/heads/main/client.py && pip3 install websockets psutil && chmod +x client.py && nohup python3 client.py -p `ip:60001,银河超算,5` &


<img width="1820" height="755" alt="{97AE4A00-7025-4882-83C8-E4B155701F7A}" src="https://github.com/user-attachments/assets/a8cd1228-0427-48df-911a-44e8c93057ce" />


![image](https://github.com/user-attachments/assets/54a17062-ec4f-4450-bd20-51186729ffe5)

# 补充
1.生成的db文件，用于储存探针数据+账号密码，如果账号密码忘记直接删除db文件即可

2.隐藏可以离线一直在连的客户端。

3.删除就是删除，但是如果客户端一直连接，db文件会新建，还会有。

4.更新client.py
>kill -9 $(ps -ef | grep "python3 client.py" | grep -v grep | awk '{print $2}')
>
>rm -f client.py && wget https://raw.githubusercontent.com/xmsssssss/smalltz/refs/heads/main/client.py
