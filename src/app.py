from flask import Flask, render_template, request, jsonify, session
import time
import os
import requests
import json
import re
from datetime import datetime
import sys

# --- 路径和模块导入 ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 假设 config.py, quantum.py 和 app.py 在同一目录
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        print(f"已将 '{current_dir}' 添加到系统路径")

    # <<< MODIFIED: 导入 config 文件
    import config
    from quantum import calculate_mastery_from_log

    print("成功导入 config 和 quantum 模块")

except ImportError as e:
    print(f"致命错误：无法导入核心模块: {e}")


    # 如果模块导入失败，定义一个兜底函数
    def calculate_mastery_from_log(data):
        return {"score": 0.0,
                "feedback": {"level": "错误", "comment": "量子模块加载失败", "suggestion": f"请检查后台服务日志: {e}"}}


    class MockConfig:
        DIFY_API_KEY = ""
        DIFY_API_URL = ""


    config = MockConfig()

# --- 路径设置 ---
project_root = os.path.dirname(current_dir)
template_dir = os.path.join(current_dir, 'templates')
LOGS_DIR = os.path.join(project_root, "logs")
print(f"模板文件夹: {template_dir}")
print(f"日志文件夹: {LOGS_DIR}")

# --- Flask 应用初始化 ---
app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)

# --- 全局配置 (已移至 config.py) ---
TIME_THRESHOLDS = {1: 8, 2: 15, 3: 25, 4: 40, 5: 60}


# <<< MODIFIED: 修正了 Dify API 调用函数
def get_dify_response(topic, user_id, conversation_id=None):
    """
    调用 Dify API 获取题目。
    修正了 payload 结构，将 topic 放入 inputs 中，这是导致 400 错误的主要原因。
    """
    headers = {
        "Authorization": f"Bearer {config.DIFY_API_KEY}",
        "Content-Type": "application/json"
    }

    # 这是正确的 payload 结构，topic 应该作为 input 变量传递
    payload = {
        "inputs": {"topic": topic},
        "query": f"请围绕 {topic} 这个主题，生成一道相关的单项选择题。",
        "user": user_id,
        "response_mode": "blocking",
        "conversation_id": conversation_id
    }

    print("\n--- 准备向 Dify 发送请求 ---")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    try:
        response = requests.post(config.DIFY_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()  # 如果请求失败 (如 400, 500), 这会抛出异常
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"!!! Dify API 调用失败: {e}")
        if e.response is not None:
            print(f"    响应状态码: {e.response.status_code}")
            print(f"    响应内容: {e.response.text}")
        return None


# --- 其余辅助函数 (无重大修改) ---
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
    threshold = TIME_THRESHOLDS.get(difficulty, 30)
    if is_correct and time_taken <= threshold:
        performance_code = '11'
    elif is_correct and time_taken > threshold:
        performance_code = '10'
    elif not is_correct and time_taken <= threshold:
        performance_code = '01'
    else:
        performance_code = '00'
    return {"difficulty": difficulty, "correctness": 1 if is_correct else 0, "performance_code": performance_code}


# --- Flask 路由 (无重大修改) ---
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
    user_id = "q-its-user-01"  # 使用固定用户ID

    if 'log_filename' not in session:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session['log_filename'] = f"session_{now}.json"
        session['session_data'] = {"topic": topic, "session_log": [], "quantum_analysis": None}
        session['topic'] = topic
        session['conversation_id'] = None  # 初始化 conversation_id

    # <<< MODIFIED: 传入 conversation_id
    dify_response = get_dify_response(session['topic'], user_id, session.get('conversation_id'))

    if not dify_response:
        return jsonify({"error": "从 Dify 服务获取数据失败, 请检查后端日志"}), 500

    raw_answer = dify_response.get('answer', '')
    session['conversation_id'] = dify_response.get('conversation_id')  # 保存新的 conversation_id

    question_package = clean_and_parse_json(raw_answer)
    if not question_package or 'difficulty' not in question_package:
        return jsonify({"error": "解析 Dify 返回的数据失败，可能格式不正确"}), 500

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


# submit-answer, end-session, get-quantum-analysis 路由与之前版本相同，无需修改
@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    print("收到请求 /submit-answer")
    if 'session_data' not in session: return jsonify({"error": "会话已过期，请刷新页面重试"}), 400
    data = request.get_json()
    user_answer_key = data.get('answer')
    time_taken = time.time() - session.get('start_time', time.time())
    current_question = session['session_data']['session_log'][-1]
    is_correct = (user_answer_key == current_question['correct_answer'])
    current_question.update({
        'user_answer': user_answer_key,
        'is_correct': is_correct,
        'time_taken': round(time_taken, 2),
        'feature_3d': calculate_3d_feature(current_question['difficulty'], is_correct, time_taken)
    })
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
    if 'session_data' not in session: return jsonify({"error": "无法找到会话信息"}), 400
    session_log = request.get_json()
    if not session_log: return jsonify({"error": "未提供用于分析的数据"}), 400

    quantum_result = calculate_mastery_from_log(session_log)
    session['session_data']['quantum_analysis'] = quantum_result
    write_log(session['log_filename'], session['session_data'])

    session.clear()
    print("量子计算和日志记录完成，会话已清理。")
    return jsonify(quantum_result)


# --- 应用启动 ---
if __name__ == '__main__':
    print("Flask 应用启动...")
    # 检查 Dify API Key 是否已配置
    if not config.DIFY_API_KEY or "YOUR_DIFY_API_KEY_HERE" in config.DIFY_API_KEY:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! 警告: Dify API Key 未在 config.py 中正确配置! !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    app.run(debug=True, host='0.0.0.0', port=5000)