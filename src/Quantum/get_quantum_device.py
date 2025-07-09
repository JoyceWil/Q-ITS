import os
from cqlib import TianYanPlatform

# 手动设置登录密钥
login_key = os.getenv("LOGIN_KEY", '43bOLKg4okCopm9zDeqUe71gyZrydhTUOjaY8rzhtCg=')
pf = TianYanPlatform(login_key=login_key)

#获取可用量子设备列表
computers = pf.query_quantum_computer_list()

print('Computers:')
print('------------------')
print(f"{'ID':<20}{'费用':<8}{'运行状态':<12}{'代码':<1}")
for item in computers:
    print(f"{str(item[0]):<20}{item[1]:<10}{item[2]:<15}{item[3]:<15}")