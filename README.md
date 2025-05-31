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

# 客户端

下载client.py
>pip3 install websockets
>
>pip3 install psutil 

>nohup python3 client.py -p ip:60001,银河超算,5

"ip:60001,银河超算,5"分别代表服务端ip、服务端ip通信端口、客户端名、定时上传间隔


![image](https://github.com/user-attachments/assets/ea48f6d2-d042-4f9f-848f-08967551a890)

![image](https://github.com/user-attachments/assets/54a17062-ec4f-4450-bd20-51186729ffe5)

