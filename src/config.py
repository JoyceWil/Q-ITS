# C:\Files\Workbench\PythonProjects\Q_ITS\src\config.py

# ==============================================================================
# Dify AI 服务配置
# ==============================================================================
# 请将这里的 key 替换为您自己的 Dify 应用 API 密钥
DIFY_API_KEY = "app-cPl9oy5CZJ4s4umWlA7SdjpT"
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"


# ==============================================================================
# 量子云平台配置 (天衍)
# ==============================================================================
# 请将这里的 key 替换为您自己的天衍平台登录密钥
TIANYAN_LOGIN_KEY = "kXCsQfkGXSX3z0yBmnlkXdFMXb3Nt6z5CXn3X4sq3tE="

# 要使用的量子计算机或模拟器名称
# 选项: "tianyan_swn" (16比特模拟器), "tianyan_sw" (36比特模拟器)
TIANYAN_MACHINE_NAME = "tianyan_sw"

# 根据所选机器自动设置比特数
MACHINE_QUBITS_MAP = {
    "tianyan_swn": 16,
    "tianyan_sw": 36
}
TIANYAN_MACHINE_QUBITS = MACHINE_QUBITS_MAP.get(TIANYAN_MACHINE_NAME, 16)

# 量子任务的测量次数 (shots)
TIANYAN_NUM_SHOTS = 2048

# RY 门角度参数的浮点数精度，以避免超出平台字符限制
TIANYAN_ANGLE_PRECISION = 12