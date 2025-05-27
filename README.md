# xmtz
一个自用python小探针

1.无安全措施

2.客户端上传无密码

3.ui垃圾

4.多端不兼容

...

---

# 服务端

打包下载，同目录直接执行以下代码：
>nohup python start.py -p "60000,60001,admin,admin"

"60000,60001,admin,admin"分别代表web端口、通信端口、web登录账号、web登录密码

# 客户端

下载client.py
>nohup python client.py -p "ip:60001,银河超算,5"

"ip:60001,银河超算,5"分别代表服务端ip、服务端ip通信端口、客户端名、定时上传间隔


![453b7483-5074-4ed1-9ca0-6f2088272dd5](https://github.com/user-attachments/assets/7d59120e-2c8a-4e99-affa-42491d96c00d)
![ace0892f-17ac-45dc-85b1-80b4898452cb](https://github.com/user-attachments/assets/e6a8b2d1-c02d-4273-90e1-8fdab78983d2)
