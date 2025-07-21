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
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        print(f"已将 '{current_dir}' 添加到系统路径")

    import config
    from quantum import calculate_mastery_from_log

    print("成功导入 config 和 quantum 模块")

except ImportError as e:
    print(f"致命错误：无法导入核心模块: {e}")


    def calculate_mastery_from_log(data):
        return {"score": 0.0,
                "feedback": {"level": "错误", "comment": "量子模块加载失败", "suggestion": f"请检查后台服务日志: {e}"}}


    class MockConfig:
        DIFY_API_KEY = ""
        DIFY_API_URL = ""


    config = MockConfig()

project_root = os.path.dirname(current_dir)
template_dir = os.path.join(current_dir, 'templates')
LOGS_DIR = os.path.join(project_root, "logs")
print(f"模板文件夹: {template_dir}")
print(f"日志文件夹: {LOGS_DIR}")


app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)

TIME_THRESHOLDS = {1: 8, 2: 15, 3: 25, 4: 40, 5: 60}


def get_dify_response(topic, user_id, conversation_id=None):
    """
    调用 Dify API 获取题目
    """
    headers = {
        "Authorization": f"Bearer {config.DIFY_API_KEY}",
        "Content-Type": "application/json"
    }

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
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"!!! Dify API 调用失败: {e}")
        if e.response is not None:
            print(f"    响应状态码: {e.response.status_code}")
            print(f"    响应内容: {e.response.text}")
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


@app.route('/')
def index():
    print("访问主页 /，清理旧会话。")
    session.clear()
    return render_template('index.html')


@app.route('/generate-question', methods=['POST'])
def generate_question():
    """
    智能处理题目生成请求：
    1. 如果是新主题，则创建全新会话。
    2. 如果是“继续强化”，则清空旧的答题记录，保留主题开始新一轮。
    """
    print("收到请求 /generate-question")
    data = request.get_json()
    topic = data.get('topic')
    is_strengthening = data.get('is_strengthening', False)  # 从前端获取强化标志

    # 场景1：这是一个“继续强化”的请求
    if is_strengthening and 'session_data' in session:
        print(f"识别为“继续强化”请求，主题: {session.get('topic')}")
        # 重置答题记录，但保留主题和会话ID
        session['session_data']['session_log'] = []
        session['session_data']['quantum_analysis'] = None
        session['start_time'] = time.time()
        print("会话日志已重置，准备开始强化学习。")

    # 场景2：这是一个全新的测试（或者会话丢失了）
    # 通过检查 log_filename 或 topic 是否匹配来判断
    elif 'log_filename' not in session or session.get('topic') != topic:
        print(f"识别为新主题测试: {topic}。正在创建全新会话。")
        session.clear()  # 开始一个新主题前，先清理旧会话
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session['log_filename'] = f"session_{now}.json"
        session['session_data'] = {"topic": topic, "session_log": [], "quantum_analysis": None}
        session['topic'] = topic
        session['conversation_id'] = None  # 新会话没有对话ID

    # 从这里开始，逻辑和之前类似，但现在会话状态是正确的
    user_id = "q-its-user-01"
    dify_response = get_dify_response(session['topic'], user_id, session.get('conversation_id'))

    if not dify_response:
        return jsonify({"error": "从 Dify 服务获取数据失败, 请检查后端日志"}), 500

    raw_answer = dify_response.get('answer', '')
    session['conversation_id'] = dify_response.get('conversation_id')

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
    session['start_time'] = time.time()  # 每次出题都重置计时器
    session.modified = True
    write_log(session['log_filename'], session['session_data'])
    return jsonify({"question_text": session_entry["question_text"], "options": session_entry["options"]})


@app.route('/get-quantum-analysis', methods=['POST'])
def get_quantum_analysis():
    """接收答题数据，进行量子计算，但不再清除会话"""
    print("收到请求 /get-quantum-analysis")

    if 'session_data' not in session or 'log_filename' not in session:
        return jsonify({"error": "无法找到会话信息以记录量子分析结果"}), 400

    session_log_from_frontend = request.get_json()
    if not session_log_from_frontend:
        return jsonify({"error": "未提供用于分析的数据"}), 400

    quantum_result = calculate_mastery_from_log(session_log_from_frontend)
    session['session_data']['quantum_analysis'] = quantum_result

    print(f"正在将量子分析结果写入日志文件: {session['log_filename']}")
    write_log(session['log_filename'], session['session_data'])

    # <<< CRITICAL CHANGE: The session.clear() line is REMOVED from here >>>
    # session.clear() # <--- DO NOT CLEAR THE SESSION HERE

    print("量子计算和日志记录完成，会话将保留用于后续操作。")
    return jsonify(quantum_result)


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

if __name__ == '__main__':
    print("Flask 应用启动...")
    # 检查 Dify API Key 是否已配置
    if not config.DIFY_API_KEY or "YOUR_DIFY_API_KEY_HERE" in config.DIFY_API_KEY:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! 警告: Dify API Key 未在 config.py 中正确配置! !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    app.run(debug=True, host='0.0.0.0', port=5000)