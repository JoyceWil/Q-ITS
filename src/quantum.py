# C:\Files\Workbench\PythonProjects\Q_ITS\src\Quantum\quantum.py

import os
import math
import json
from datetime import datetime

try:
    import config
    from cqlib import TianYanPlatform, Circuit
except ImportError:
    print("错误：cqlib 库或 config 文件未安装或未找到。")


    class TianYanPlatform:
        pass


    class Circuit:
        pass


    class MockConfig:
        TIANYAN_LOGIN_KEY = ""
        TIANYAN_NUM_SHOTS = 2048
        TIANYAN_MACHINE_NAME = "tianyan_swn"
        TIANYAN_MACHINE_QUBITS = 16
        TIANYAN_ANGLE_PRECISION = 12


    config = MockConfig()

def get_mastery_feedback(score):
    if score >= 0.85: return {"level": "大师精通", "comment": "表现卓越！您已完全掌握了这部分知识。",
                              "suggestion": "太棒了！试试挑战一些更深或更广的难题吧！"}
    if score >= 0.50: return {"level": "熟练应用", "comment": "非常不错！您已经相当熟练了。",
                              "suggestion": "保持状态，建议再练习几次来彻底巩固。"}
    if score >= 0.20: return {"level": "基础学习", "comment": "有了一个不错的开始，但基础还需加强。",
                              "suggestion": "您的基础还比较薄弱。建议回顾知识点，多做几轮练习。"}
    return {"level": "知识萌芽", "comment": "看起来您已经掌握了部分知识。",
            "suggestion": "再接再励，先仔细学习相关的知识点，弄懂概念后再来尝试。"}

def calculate_mastery_from_log(session_data):
    print(f"\n--- [{datetime.now()}] Quantum Analyzer: 开始处理会话数据 ---")
    if not session_data:
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

    classic_scores = []
    for item in session_data:
        feature = item.get('feature_3d')
        if not feature: continue
        d_map = {1: 0b00, 2: 0b01, 3: 0b10, 4: 0b11, 5: 0b11}
        d_code = d_map.get(feature['difficulty'], 0b00)
        p_code = int(feature['performance_code'], 2)
        score = (d_code << 2) | p_code
        classic_scores.append(score)
        print(
            f"  - 题目 {item.get('question_num')}: 难度={feature['difficulty']}, 表现='{feature['performance_code']}' -> 综合分 = {score}/15")

    if not classic_scores:
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

    num_active_qubits = len(classic_scores)

    # <<< MODIFIED: 使用 config 中的变量
    if num_active_qubits > config.TIANYAN_MACHINE_QUBITS:
        error_msg = f"用户答题数({num_active_qubits})超过了所选机器 '{config.TIANYAN_MACHINE_NAME}' 的容量({config.TIANYAN_MACHINE_QUBITS})。"
        print(f"--- Quantum Analyzer: 严重错误: {error_msg}")
        return {"score": 0.0,
                "feedback": {"level": "系统错误", "comment": error_msg, "suggestion": "请减少答题数量或联系管理员。"}}

    print(
        f"--- Quantum Analyzer: 已生成 {num_active_qubits} 个经典分数。将构建一个 {config.TIANYAN_MACHINE_QUBITS} 比特的电路以适配 '{config.TIANYAN_MACHINE_NAME}'。")
    print(f"--- Quantum Analyzer: 正在将角度参数四舍五入到 {config.TIANYAN_ANGLE_PRECISION} 位小数...")
    thetas = [round((s / 15.0) * math.pi, config.TIANYAN_ANGLE_PRECISION) for s in classic_scores]

    print("--- Quantum Analyzer: 正在构建量子电路...")
    q_circuit = Circuit(list(range(config.TIANYAN_MACHINE_QUBITS)))

    for i, theta in enumerate(thetas):
        q_circuit.ry(i, theta)

    if num_active_qubits > 1:
        print("--- Quantum Analyzer: 正在应用纠缠门 (手动分解 CX 为 H-CZ-H)...")
        for i in range(num_active_qubits - 1):
            q_circuit.h(i + 1)
            q_circuit.cz(i, i + 1)
            q_circuit.h(i + 1)

    print(f"--- Quantum Analyzer: 只精确测量 {num_active_qubits} 个活动量子比特...")
    for i in range(num_active_qubits):
        q_circuit.measure(i)

    print("--- Quantum Analyzer: 电路构建完成。")

    try:
        print(f"--- Quantum Analyzer: 正在连接天衍平台并提交任务至模拟器 '{config.TIANYAN_MACHINE_NAME}'...")
        platform = TianYanPlatform(login_key=config.TIANYAN_LOGIN_KEY, machine_name=config.TIANYAN_MACHINE_NAME)
        query_id = platform.submit_experiment(q_circuit.qcis, num_shots=config.TIANYAN_NUM_SHOTS)
        print(f"  - 任务提交成功, Query ID: {query_id}")
        data = platform.query_experiment(query_id)
        # print(f"--- Quantum Analyzer: 从平台接收到的原始数据:\n{json.dumps(data, indent=2, ensure_ascii=False)}")

        if not data or 'probability' not in data[0]:
            raise ValueError("从平台查询到的任务结果为空或格式不正确。")

        results = json.loads(data[0]['probability'])
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
    pass