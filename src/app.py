from flask import Flask, render_template, request, jsonify, session
import time
import os
import requests
import json
import re
from datetime import datetime
import sys


try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(src_dir)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        print(f"已将 '{src_dir}' 添加到系统路径")
    template_dir = os.path.join(src_dir, 'src', 'templates')
    LOGS_DIR = os.path.join(project_root, "logs")
    print(f"项目根目录: {project_root}")
    print(f"模板文件夹: {template_dir}")
    print(f"日志文件夹: {LOGS_DIR}")
    if not os.path.isdir(template_dir):
        print(f"警告：模板文件夹 '{template_dir}' 不存在！")
except Exception as e:
    print(f"路径设置时发生错误: {e}")
    template_dir = '../../templates'
    LOGS_DIR = '../logs'

try:
    from quantum import calculate_mastery_from_log

    print("成功从 Quantum.quantum 导入 calculate_mastery_from_log")
except ImportError as e:
    print(f"错误：无法导入量子计算模块: {e}")


    def calculate_mastery_from_log(data):
        return {"score": 0.0,
                "feedback": {"level": "错误", "comment": "量子模块加载失败", "suggestion": "请检查后台服务日志"}}

# --- Flask 应用初始化 ---
app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)

# --- 全局配置 ---
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "app-HNvHtsBE4IelskEEq6xRZmSS")
TIME_THRESHOLDS = {1: 8, 2: 15, 3: 25, 4: 40, 5: 60}


def get_dify_response(topic, user_id):
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}", "Content-Type": "application/json"}
    payload = {"inputs": {}, "query": topic, "user": user_id, "response_mode": "blocking"}
    try:
        response = requests.post(DIFY_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get('answer')
    except requests.exceptions.RequestException as e:
        print(f"API 调用失败: {e}")
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
    os.makedirs(LOGS_DIR, exist_ok=True)
    filepath = os.path.join(LOGS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_3d_feature(difficulty, is_correct, time_taken):
    difficulty_score = difficulty
    correctness_score = 1 if is_correct else 0
    threshold = TIME_THRESHOLDS.get(difficulty, 30)
    is_in_time = time_taken <= threshold
    if is_in_time and is_correct:
        performance_code = '11'
    elif not is_in_time and is_correct:
        performance_code = '10'
    elif is_in_time and not is_correct:
        performance_code = '01'
    else:
        performance_code = '00'
    return {"difficulty": difficulty_score, "correctness": correctness_score, "performance_code": performance_code}


@app.route('/')
def index():
    print("访问主页 /，清理旧会话。")
    session.clear()
    return render_template('index.html')


@app.route('/generate-question', methods=['POST'])
def generate_question():
    print("收到请求 /generate-question")
    data = request.get_json()
    if not data or 'topic' not in data:
        return jsonify({"error": "请求中缺少主题"}), 400

    topic = data.get('topic')
    user_id = "web-user-session-1"

    if 'log_filename' not in session:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session['log_filename'] = f"session_{now}.json"

        session['session_data'] = {
            "topic": topic,
            "session_log": [],
            "quantum_analysis": None  # 初始为 null
        }
        session['topic'] = topic

    raw_answer = get_dify_response(session['topic'], user_id)
    if not raw_answer:
        return jsonify({"error": "从 Dify 服务获取数据失败"}), 500

    question_package = clean_and_parse_json(raw_answer)
    if not question_package or 'difficulty' not in question_package:
        return jsonify({"error": "解析 Dify 返回的数据失败"}), 500

    question_num = len(session['session_data']['session_log']) + 1
    session_entry = {
        "question_num": question_num, "question_text": question_package.get('question'),
        "options": question_package.get('options'), "correct_answer": question_package.get('correct_answer'),
        "explanation": question_package.get('explanation'), "difficulty": question_package.get('difficulty'),
        "user_answer": None, "is_correct": None, "time_taken": None, "feature_3d": None
    }

    session['session_data']['session_log'].append(session_entry)
    session['start_time'] = time.time()
    session.modified = True

    write_log(session['log_filename'], session['session_data'])

    return jsonify({"question_text": session_entry["question_text"], "options": session_entry["options"]})


@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    print("收到请求 /submit-answer")
    if 'session_data' not in session:
        return jsonify({"error": "会话已过期，请刷新页面重试"}), 400

    data = request.get_json()
    user_answer_key = data.get('answer')
    time_taken = time.time() - session.get('start_time', time.time())

    current_question = session['session_data']['session_log'][-1]

    is_correct = (user_answer_key == current_question['correct_answer'])
    current_question['user_answer'] = user_answer_key
    current_question['is_correct'] = is_correct
    current_question['time_taken'] = round(time_taken, 2)
    difficulty = current_question['difficulty']
    feature = calculate_3d_feature(difficulty, is_correct, time_taken)
    current_question['feature_3d'] = feature

    session.modified = True
    write_log(session['log_filename'], session['session_data'])

    return jsonify({"status": "ok"})


@app.route('/end-session', methods=['POST'])
def end_session():
    """结束会话，返回经典的答题报告"""
    print("收到请求 /end-session")
    if 'session_data' not in session:
        return jsonify({"error": "会话已过期或无数据"}), 400

    final_data = session.get('session_data', {}).get('session_log', [])

    return jsonify(final_data)


@app.route('/get-quantum-analysis', methods=['POST'])
def get_quantum_analysis():
    """接收答题数据，进行量子计算，更新日志并返回结果"""
    print("收到请求 /get-quantum-analysis")

    # 增加对后端会话的检查
    if 'session_data' not in session or 'log_filename' not in session:
        return jsonify({"error": "无法找到会话信息以记录量子分析结果"}), 400

    session_log_from_frontend = request.get_json()
    if not session_log_from_frontend:
        return jsonify({"error": "未提供用于分析的数据"}), 400

    # 调用量子计算模块
    quantum_result = calculate_mastery_from_log(session_log_from_frontend)

    session['session_data']['quantum_analysis'] = quantum_result

    print(f"正在将最终结果写入日志文件: {session['log_filename']}")
    write_log(session['log_filename'], session['session_data'])

    # 计算和记录完成后，现在可以安全清理会话
    session.clear()
    print("量子计算和日志记录完成，会话已清理。")

    return jsonify(quantum_result)


# 应用启动
if __name__ == '__main__':
    print("Flask 应用启动...")
    app.run(debug=True, host='0.0.0.0', port=5000)