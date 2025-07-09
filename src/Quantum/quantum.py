import os
import math
import json
from datetime import datetime

from cqlib import TianYanPlatform, Circuit

# 配置项
LOGIN_KEY = os.getenv("TIANYAN_LOGIN_KEY", "")
MACHINE_NAME = "tianyan_sw"
NUM_SHOTS = 2048


# 掌握度评估函数
def get_mastery_feedback(score):
    """
    根据量子掌握度分数，返回对应的评级、评语和建议。

    Args:
        score (float): 一个介于 0.0 和 1.0 之间的掌握度分数。

    Returns:
        dict: 包含 'level', 'comment', 和 'suggestion' 的字典。
    """
    if score >= 0.85:
        return {
            "level": "大师精通",
            "comment": "表现卓越！您已完全掌握了这部分知识。",
            "suggestion": "太棒了！试试挑战一些更深或更广的难题来扩展您的知识边界吧！"
        }
    elif score >= 0.50:
        return {
            "level": "熟练应用",
            "comment": "非常不错！您已经相当熟练了。",
            "suggestion": "保持状态，建议再练习几次来彻底巩固，或者开始探索相关的新知识点。"
        }
    elif score >= 0.20:
        return {
            "level": "基础学习",
            "comment": "有了一个不错的开始，但还需多加练习。",
            "suggestion": "您已经基本了解这些知识。建议您回顾一下相关的基础知识点，然后多做几轮练习来加深理解。"
        }
    else:
        return {
            "level": "知识萌芽",
            "comment": "看起来您对这部分知识还不太熟悉。",
            "suggestion": "没关系，每个大师都是从这里开始的。强烈建议您先仔细学习一下相关的知识点，弄懂基本概念后再来尝试练习。"
        }


# 核心计算函数
def calculate_mastery_from_log(session_data):
    """
    接收会话日志，执行量子计算，并返回分数和反馈。
    """
    if not session_data:
        print("--- Quantum Analyzer: 错误 - 传入的会话数据为空。")
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

    # 步骤 1: 经典特征 -> 经典综合分数 (0-15)
    classic_scores = []
    for item in session_data:
        feature = item.get('feature_3d')
        if not feature:
            print(f"--- Quantum Analyzer: 警告 - 题目 {item.get('question_num')} 缺少 'feature_3d'，已跳过。")
            continue
        difficulty = feature['difficulty']
        d_map = {1: 0b00, 2: 0b01, 3: 0b10, 4: 0b11, 5: 0b11}
        d_code = d_map.get(difficulty, 0b00)
        p_code = int(feature['performance_code'], 2)
        score = (d_code << 2) | p_code
        classic_scores.append(score)
        print(
            f"  - 题目 {item.get('question_num')}: 难度={difficulty}, 表现='{feature['performance_code']}' -> 综合分 = {score}/15")

    if not classic_scores:
        print("--- Quantum Analyzer: 错误 - 没有可用于计算的有效特征数据。")
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

    num_questions = len(classic_scores)
    print(f"--- Quantum Analyzer: 已生成 {num_questions} 个题目的经典分数。")

    # 步骤 2: 角度编码
    thetas = [(s / 15.0) * math.pi for s in classic_scores]

    # 步骤 3: 构建量子电路
    print("--- Quantum Analyzer: 正在构建量子电路...")
    q_circuit = Circuit(list(range(num_questions)))
    for i, theta in enumerate(thetas):
        q_circuit.ry(i, theta)
    if num_questions > 1:
        for i in range(num_questions - 1):
            q_circuit.cx(i, i + 1)
    q_circuit.measure_all()
    print("--- Quantum Analyzer: 电路构建完成。")
    print(q_circuit.draw()) # 在调试时可以取消注释来查看电路图

    # 步骤 4: 连接云平台，提交任务并获取结果
    try:
        print(f"--- Quantum Analyzer: 正在连接天衍平台并提交任务至模拟器 '{MACHINE_NAME}'...")
        platform = TianYanPlatform(login_key=LOGIN_KEY, machine_name=MACHINE_NAME)
        query_id = platform.submit_experiment(q_circuit.qcis, num_shots=NUM_SHOTS)
        print(f"  - 任务提交成功, Query ID: {query_id}")
        data = platform.query_experiment(query_id)

        if not data or 'probability' not in data[0]:
            print("--- Quantum Analyzer: 错误 - 从平台查询到的任务结果为空或格式不正确。")
            return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}

        probability_data = data[0]['probability']
        if isinstance(probability_data, str):
            results = json.loads(probability_data)
        else:
            results = probability_data

        print(f"  - 任务计算完成，已成功解析概率分布结果。")

        # 步骤 5: 解读结果，计算最终掌握度
        all_ones_state = '1' * num_questions
        mastery_score = results.get(all_ones_state, 0.0)

        print(f"--- Quantum Analyzer: 最终掌握度 (测量到 '{all_ones_state}' 的概率) = {mastery_score:.4f} ---")

        # 步骤 6: 获取反馈
        feedback = get_mastery_feedback(mastery_score)
        print(f"--- Quantum Analyzer: 评估等级: {feedback['level']} ---")

        return {"score": mastery_score, "feedback": feedback}

    except Exception as e:
        print(f"--- Quantum Analyzer: 量子计算过程中发生严重错误: {e}")
        return {"score": 0.0, "feedback": get_mastery_feedback(0.0)}



# 用于独立测试的示例代码

if __name__ == '__main__':
    print("--- 正在以独立模式运行 quantum.py 进行测试 ---")

    test_log_data = [
        {"correct_answer": "A", "difficulty": 3, "feature_3d": {"difficulty": 3, "performance_code": "11"},
         "question_num": 1},
        {"correct_answer": "A", "difficulty": 2, "feature_3d": {"difficulty": 2, "performance_code": "11"},
         "question_num": 2},
        {"correct_answer": "A", "difficulty": 1, "feature_3d": {"difficulty": 1, "performance_code": "11"},
         "question_num": 3},
        {"correct_answer": "C", "difficulty": 1, "feature_3d": {"difficulty": 1, "performance_code": "11"},
         "question_num": 8}
    ]

    # 调用核心函数进行计算
    final_result = calculate_mastery_from_log(test_log_data)

    print("\n--- 测试完成 ---")
    print(f"最终返回的完整结果: {json.dumps(final_result, ensure_ascii=False, indent=2)}")
