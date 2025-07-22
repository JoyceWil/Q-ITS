# 文件: src/app.py

import os
import sys
import json
import re
import time
from datetime import datetime
import requests
import certifi
from flask import Flask, render_template, request, jsonify, session


# --- 1. 路径智能检测与设置 (这是唯一需要定义路径的地方) ---
def get_resource_path(relative_path):
    """ 获取资源的绝对路径，无论是开发环境还是打包后 """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_writable_path(relative_path):
    """ 获取一个可写入的路径，始终以可执行文件或主脚本的位置为基准 """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base_path, relative_path)


# 使用新函数定义路径
template_dir = get_resource_path('templates')
LOGS_DIR = get_writable_path('logs')

# 确保日志目录存在
try:
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"日志目录已确认/创建于: {LOGS_DIR}")
except OSError as e:
    print(f"错误：无法创建日志目录 {LOGS_DIR}。错误信息: {e}")

# --- 2. 模块导入与容错处理 (您的优秀设计) ---
try:
    # 将当前目录添加到 sys.path 以帮助 PyInstaller 找到模块
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    import config
    from quantum import calculate_mastery_from_log

    print("成功导入 config 和 quantum 模块")

except ImportError as e:
    print(f"致命错误：无法导入核心模块: {e}")


    # 创建降级函数和配置
    def calculate_mastery_from_log(data):
        return {"score": 0.0,
                "feedback": {"level": "错误", "comment": "量子模块加载失败", "suggestion": f"请检查后台服务日志: {e}"}}


    class MockConfig:
        DIFY_API_KEY = ""
        DIFY_API_URL = ""


    config = MockConfig()

# --- 3. Flask 应用初始化 ---
app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)


def get_dify_response(topic, user_id, conversation_id=None):
    headers = {"Authorization": f"Bearer {config.DIFY_API_KEY}", "Content-Type": "application/json"}
    payload = {"inputs": {"topic": topic}, "query": f"请围绕 {topic} 这个主题，生成一道相关的单项选择题。",
               "user": user_id, "response_mode": "blocking", "conversation_id": conversation_id}
    print(f"\n--- 准备向 Dify 发送请求 ---\nPayload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    try:
        # --- CRITICAL FIX: 添加 verify=certifi.where() ---
        # 2. 在 post 请求中，明确指定使用 certifi 提供的证书进行验证
        response = requests.post(config.DIFY_API_URL, headers=headers, json=payload, timeout=120, verify=certifi.where())
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"!!! Dify API 调用失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"    响应状态码: {e.response.status_code}\n    响应内容: {e.response.text}")
        return None


def clean_and_parse_json(raw_string):
    if not isinstance(raw_string, str): return None
    match = re.search(r'\{.*\}', raw_string, re.DOTALL)
    if not match: return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}\n原始字符串: {match.group(0)}")
        return None


def write_log(filename, data):
    # 此函数现在会使用在文件顶部定义的、正确的 LOGS_DIR
    filepath = os.path.join(LOGS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_3d_feature(difficulty, is_correct, time_taken):
    # --- CRITICAL FIX: 使用 config.TIME_THRESHOLDS ---
    threshold = config.TIME_THRESHOLDS.get(difficulty, 30) # 从 config 获取阈值
    if is_correct and time_taken <= threshold:
        performance_code = '11'
    elif is_correct and time_taken > threshold:
        performance_code = '10'
    elif not is_correct and time_taken <= threshold:
        performance_code = '01'
    else:
        performance_code = '00'
    return {"difficulty": difficulty, "correctness": 1 if is_correct else 0, "performance_code": performance_code}


# --- 5. Flask 路由 ---
@app.route('/')
def index():
    print("访问主页 /，清理旧会话。")
    session.clear()
    return render_template('index.html')


@app.route('/generate-question', methods=['POST'])
def generate_question():
    print("收到请求 /generate-question")
    data = request.get_json()
    topic = data.get('topic')
    is_strengthening = data.get('is_strengthening', False)
    if is_strengthening and 'session_data' in session:
        print(f"识别为“继续强化”请求，主题: {session.get('topic')}")
        session['session_data']['session_log'] = []
        session['session_data']['quantum_analysis'] = None
        session['start_time'] = time.time()
    elif 'log_filename' not in session or session.get('topic') != topic:
        print(f"识别为新主题测试: {topic}。正在创建全新会话。")
        session.clear()
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session['log_filename'] = f"session_{now}.json"
        session['session_data'] = {"topic": topic, "session_log": [], "quantum_analysis": None}
        session['topic'] = topic
        session['conversation_id'] = None
    user_id = "q-its-user-01"
    dify_response = get_dify_response(session['topic'], user_id, session.get('conversation_id'))
    if not dify_response: return jsonify({"error": "从 Dify 服务获取数据失败, 请检查后端日志"}), 500
    raw_answer = dify_response.get('answer', '')
    session['conversation_id'] = dify_response.get('conversation_id')
    question_package = clean_and_parse_json(raw_answer)
    if not question_package or 'difficulty' not in question_package: return jsonify(
        {"error": "解析 Dify 返回的数据失败，可能格式不正确"}), 500
    question_num = len(session['session_data']['session_log']) + 1
    session_entry = {"question_num": question_num, "question_text": question_package.get('question'),
                     "options": question_package.get('options'),
                     "correct_answer": question_package.get('correct_answer'),
                     "explanation": question_package.get('explanation'),
                     "difficulty": question_package.get('difficulty'), "user_answer": None, "is_correct": None,
                     "time_taken": None, "feature_3d": None}
    session['session_data']['session_log'].append(session_entry)
    session['start_time'] = time.time()
    session.modified = True
    write_log(session['log_filename'], session['session_data'])
    return jsonify({"question_text": session_entry["question_text"], "options": session_entry["options"]})


@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    print("收到请求 /submit-answer")
    if 'session_data' not in session: return jsonify({"error": "会话已过期，请刷新页面重试"}), 400
    data = request.get_json()
    user_answer_key = data.get('answer')
    time_taken = time.time() - session.get('start_time', time.time())
    current_question = session['session_data']['session_log'][-1]
    is_correct = (user_answer_key == current_question['correct_answer'])
    current_question.update(
        {'user_answer': user_answer_key, 'is_correct': is_correct, 'time_taken': round(time_taken, 2),
         'feature_3d': calculate_3d_feature(current_question['difficulty'], is_correct, time_taken)})
    session.modified = True
    write_log(session['log_filename'], session['session_data'])
    return jsonify({"status": "ok"})


@app.route('/end-session', methods=['POST'])
def end_session():
    print("收到请求 /end-session")
    if 'session_data' not in session: return jsonify({"error": "会话已过期或无数据"}), 400
    return jsonify(session.get('session_data', {}).get('session_log', []))


@app.route('/get-quantum-analysis', methods=['POST'])
def get_quantum_analysis():
    print("收到请求 /get-quantum-analysis")
    if 'session_data' not in session or 'log_filename' not in session: return jsonify(
        {"error": "无法找到会话信息以记录量子分析结果"}), 400
    session_log_from_frontend = request.get_json()
    if not session_log_from_frontend: return jsonify({"error": "未提供用于分析的数据"}), 400
    quantum_result = calculate_mastery_from_log(session_log_from_frontend)
    session['session_data']['quantum_analysis'] = quantum_result
    print(f"正在将量子分析结果写入日志文件: {session['log_filename']}")
    write_log(session['log_filename'], session['session_data'])
    print("量子计算和日志记录完成，会话将保留用于后续操作。")
    return jsonify(quantum_result)


# --- 6. 应用启动入口 ---
if __name__ == '__main__':
    print("Flask 应用直接启动 (用于Web开发调试)...")
    if not config.DIFY_API_KEY in config.DIFY_API_KEY:
        print("!!! 警告: Dify API Key 未在 config.py 中正确配置! !!!")
    app.run(debug=True, host='0.0.0.0', port=5000)