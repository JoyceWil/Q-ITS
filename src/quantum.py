# C:\Files\Workbench\PythonProjects\Q_ITS\src\Quantum\quantum.py

import os
import math
import json
from datetime import datetime

try:
    from cqlib import TianYanPlatform, Circuit
except ImportError:
    print("错误：cqlib 库未安装或未找到。")


    class TianYanPlatform:
        pass


    class Circuit:
        pass

# --- 配置项 (最终版) ---
LOGIN_KEY = os.getenv("TIANYAN_LOGIN_KEY", "kXCsQfkGXSX3z0yBmnlkXdFMXb3Nt6z5CXn3X4sq3tE=")
NUM_SHOTS = 2048
MACHINE_NAME = "tianyan_sw"
MACHINE_QUBITS = 36
ANGLE_PRECISION = 12  # 设置一个安全的角度精度，确保字符长度小于15


# ==============================================================================
# 掌握度评估函数 (无变化)
# ==============================================================================
def get_mastery_feedback(score):
    if score >= 0.85: return {"level": "大师精通", "comment": "表现卓越！您已完全掌握了这部分知识。",
                              "suggestion": "太棒了！试试挑战一些更深或更广的难题吧！"}
    if score >= 0.50: return {"level": "熟练应用", "comment": "非常不错！您已经相当熟练了。",
                              "suggestion": "保持状态，建议再练习几次来彻底巩固。"}
    if score >= 0.20: return {"level": "基础学习", "comment": "有了一个不错的开始，但基础还需加强。",
                              "suggestion": "您的基础还比较薄弱。建议回顾知识点，多做几轮练习。"}
    return {"level": "知识萌芽", "comment": "看起来您对这部分知识还不太熟悉。",
            "suggestion": "没关系，先仔细学习相关的知识点，弄懂概念后再来尝试。"}


# ==============================================================================
# 核心计算函数 (最终正确版本)
# ==============================================================================
def calculate_mastery_from_log(session_data):
    print(f"\n--- [{datetime.now()}] Quantum Analyzer: 开始处理会话数据 ---")
    if not session_data:
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

    classic_scores = []
    for item in session_data:
        feature = item.get('feature_3d')
        if not feature: continue
        difficulty = feature['difficulty']
        d_map = {1: 0b00, 2: 0b01, 3: 0b10, 4: 0b11, 5: 0b11}
        d_code = d_map.get(difficulty, 0b00)
        p_code = int(feature['performance_code'], 2)
        score = (d_code << 2) | p_code
        classic_scores.append(score)
        print(
            f"  - 题目 {item.get('question_num')}: 难度={difficulty}, 表现='{feature['performance_code']}' -> 综合分 = {score}/15")

    if not classic_scores:
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

    num_active_qubits = len(classic_scores)

    if num_active_qubits > MACHINE_QUBITS:
        error_msg = f"用户答题数({num_active_qubits})超过了所选机器 '{MACHINE_NAME}' 的容量({MACHINE_QUBITS})。"
        print(f"--- Quantum Analyzer: 严重错误: {error_msg}")
        return {"score": 0.0,
                "feedback": {"level": "系统错误", "comment": error_msg, "suggestion": "请减少答题数量或联系管理员。"}}

    print(
        f"--- Quantum Analyzer: 已生成 {num_active_qubits} 个经典分数。将构建一个 {MACHINE_QUBITS} 比特的电路以适配 '{MACHINE_NAME}'。")

    # --- 关键修改：将角度四舍五入到指定精度，以满足平台15个字符的限制 ---
    print(f"--- Quantum Analyzer: 正在将角度参数四舍五入到 {ANGLE_PRECISION} 位小数...")
    thetas = [round((s / 15.0) * math.pi, ANGLE_PRECISION) for s in classic_scores]

    print("--- Quantum Analyzer: 正在构建量子电路...")
    q_circuit = Circuit(list(range(MACHINE_QUBITS)))

    for i, theta in enumerate(thetas):
        q_circuit.ry(i, theta)

    if num_active_qubits > 1:
        print("--- Quantum Analyzer: 正在应用纠缠门 (手动分解 CX 为 H-CZ-H)...")
        for i in range(num_active_qubits - 1):
            target_qubit = i + 1
            control_qubit = i
            q_circuit.h(target_qubit)
            q_circuit.cz(control_qubit, target_qubit)
            q_circuit.h(target_qubit)

    print(f"--- Quantum Analyzer: 只精确测量 {num_active_qubits} 个活动量子比特...")
    for i in range(num_active_qubits):
        q_circuit.measure(i)

    print("--- Quantum Analyzer: 电路构建完成。")

    try:
        print(f"--- Quantum Analyzer: 正在连接天衍平台并提交任务至模拟器 '{MACHINE_NAME}'...")
        platform = TianYanPlatform(login_key=LOGIN_KEY, machine_name=MACHINE_NAME)
        query_id = platform.submit_experiment(q_circuit.qcis, num_shots=NUM_SHOTS)
        print(f"  - 任务提交成功, Query ID: {query_id}")
        data = platform.query_experiment(query_id)

        print(f"--- Quantum Analyzer: 从平台接收到的原始数据:\n{json.dumps(data, indent=2, ensure_ascii=False)}")

        if not data or 'probability' not in data[0]:
            raise ValueError("从平台查询到的任务结果为空或格式不正确。")

        probability_data = data[0]['probability']
        results = json.loads(probability_data) if isinstance(probability_data, str) else probability_data
        print(f"  - 任务计算完成，已成功解析概率分布结果。")

        all_ones_state = '1' * num_active_qubits
        mastery_score = results.get(all_ones_state, 0.0)

        print(f"--- Quantum Analyzer: 最终掌握度 (测量到 '{all_ones_state}' 的概率) = {mastery_score:.4f} ---")

        feedback = get_mastery_feedback(mastery_score)
        print(f"--- Quantum Analyzer: 评估等级: {feedback['level']} ---")

        return {"score": mastery_score, "feedback": feedback}

    except Exception as e:
        print(f"--- Quantum Analyzer: 量子计算过程中发生严重错误: {e}")
        return {"score": 0.0, "feedback": {"level": "计算错误", "comment": "在与量子平台通信时发生错误。",
                                           "suggestion": f"请检查后台日志。错误摘要: {str(e)}"}}


# ==============================================================================
# 用于独立测试的示例代码
# ==============================================================================
if __name__ == '__main__':
    print("--- 正在以独立模式运行 quantum.py 进行测试 ---")

    test_log_data = [
        {"correct_answer": "A", "difficulty": 3, "explanation": "...",
         "feature_3d": {"correctness": 1, "difficulty": 3, "performance_code": "11"}, "is_correct": True, "options": {},
         "question_num": 1, "question_text": "...", "time_taken": 4.61, "user_answer": "A"},
        {"correct_answer": "A", "difficulty": 2, "explanation": "...",
         "feature_3d": {"correctness": 1, "difficulty": 2, "performance_code": "11"}, "is_correct": True, "options": {},
         "question_num": 2, "question_text": "...", "time_taken": 3.8, "user_answer": "A"},
        {"correct_answer": "A", "difficulty": 1, "explanation": "...",
         "feature_3d": {"correctness": 1, "difficulty": 1, "performance_code": "11"}, "is_correct": True, "options": {},
         "question_num": 3, "question_text": "...", "time_taken": 1.32, "user_answer": "A"},
        {"correct_answer": "C", "difficulty": 1, "explanation": "...",
         "feature_3d": {"difficulty": 1, "correctness": 1, "performance_code": "11"}, "is_correct": True, "options": {},
         "question_num": 4, "question_text": "...", "time_taken": 2.91, "user_answer": "C"}
    ]

    final_score = calculate_mastery_from_log(test_log_data)

    print("\n--- 测试完成 ---")
    print(f"最终计算出的掌握度分数为: {final_score}")