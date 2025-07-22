# 文件: src/desktop.py

import sys
import os
import webview
import threading
from datetime import datetime


# --- 日志重定向 (关键新增部分) ---
# 定义一个类，它会将所有写入操作重定向到文件和原始终端
class Logger(object):
    def __init__(self, filename="q-its-debug.log"):
        # 获取.exe文件所在的目录来存放日志
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        self.log_file_path = os.path.join(base_path, filename)
        self.terminal = sys.stdout
        self.log = open(self.log_file_path, "a", encoding='utf-8')  # 使用追加模式
        self.log.write(f"\n\n--- Log started at {datetime.now()} ---\n")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()  # 确保立即写入文件

    def flush(self):
        self.terminal.flush()
        self.log.flush()


# 在导入任何我们自己的模块之前，就重定向 stdout 和 stderr
sys.stdout = Logger()
sys.stderr = sys.stdout  # 将错误输出也重定向到同一个地方

print("--- 启动脚本 run_desktop.py 开始执行 ---")
print(f"Python 版本: {sys.version}")
print(f"程序可执行文件/脚本路径: {sys.executable if getattr(sys, 'frozen', False) else __file__}")

# 现在才导入我们的 Flask 应用
from app import app


# 定义一个函数来在后台线程中运行 Flask 服务器
def run_server():
    print("--- Flask 服务器线程已启动 ---")
    # 注意：我们不再使用 werkzeug 的 run_simple，因为在打包后可能会有问题
    # 直接使用 app.run() 并禁用重载器是更稳定的选择
    try:
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
        print("--- Flask 服务器线程已正常退出 ---")
    except Exception as e:
        print(f"!!!!!! Flask 服务器线程崩溃 !!!!!!")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        # 打印完整的错误堆栈
        import traceback
        traceback.print_exc(file=sys.stdout)


if __name__ == '__main__':
    print("--- 主程序入口 __main__ ---")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("--- 后台服务器线程已创建并启动 ---")

    webview.create_window(
        '量子增强智能导学系统 Q-ITS (调试模式)',
        'http://127.0.0.1:5000',
        width=850,
        height=700,
        resizable=True,
        min_size=(600, 500)
    )

    print("--- PyWebView 窗口已创建 ---")
    webview.start(debug=True)  # 开启 webview 的调试模式
    print("--- PyWebView 事件循环已结束，程序即将退出 ---")