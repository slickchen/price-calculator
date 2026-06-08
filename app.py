"""
TRE Price Calculator - Web版
Flask后端，支持手机浏览器访问
"""

from flask import Flask, render_template, request, jsonify
from calculator import PriceCalculator, Session, Person
import os

app = Flask(__name__)
calc = PriceCalculator()

# 全局会话存储（内存+文件持久化）
sessions = {}


def get_or_create_session(session_id: str) -> Session:
    """获取或创建会话"""
    if session_id not in sessions:
        # 尝试从文件加载
        saves = calc.list_saves()
        for save in saves:
            if save['filename'].replace('.json', '') == session_id:
                calc.load_session(save['filepath'])
                sessions[session_id] = calc.session
                return calc.session
        # 新建
        calc.new_session(session_id)
        sessions[session_id] = calc.session
    return sessions[session_id]


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """列出所有会话"""
    saves = calc.list_saves()
    return jsonify(saves)


@app.route('/api/sessions', methods=['POST'])
def create_session():
    """新建会话"""
    data = request.json or {}
    name = data.get('name', '')
    session = calc.new_session(name)
    session_id = session.name
    sessions[session_id] = session
    # 保存到文件
    calc.save_session()
    return jsonify({
        'id': session_id,
        'name': session.name,
        'created_at': session.created_at
    })


@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取会话详情"""
    session = get_or_create_session(session_id)
    return jsonify(session_to_dict(session))


@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除会话"""
    if session_id in sessions:
        del sessions[session_id]
    # 删除文件
    saves = calc.list_saves()
    for save in saves:
        if save['filename'].replace('.json', '') == session_id:
            calc.delete_save(save['filepath'])
            break
    return jsonify({'ok': True})


@app.route('/api/sessions/<session_id>/persons', methods=['POST'])
def add_person(session_id):
    """添加客户"""
    session = get_or_create_session(session_id)
    data = request.json or {}
    name = data.get('name', '')
    if not name:
        return jsonify({'error': '姓名不能为空'}), 400
    person = session.add_person(name)
    auto_save(session_id)
    return jsonify(person_to_dict(person, session))


@app.route('/api/sessions/<session_id>/persons/<int:person_idx>', methods=['DELETE'])
def remove_person(session_id, person_idx):
    """删除客户"""
    session = get_or_create_session(session_id)
    session.remove_person(person_idx)
    auto_save(session_id)
    return jsonify({'ok': True})


@app.route('/api/sessions/<session_id>/persons/<int:person_idx>/clock', methods=['POST'])
def add_clock(session_id, person_idx):
    """添加卡钟费用"""
    session = get_or_create_session(session_id)
    person = session.get_person(person_idx)
    if not person:
        return jsonify({'error': '客户不存在'}), 404
    data = request.json or {}
    try:
        fee = float(data.get('fee', 0))
        if fee <= 0:
            return jsonify({'error': '金额必须大于0'}), 400
        person.add_clock_fee(fee)
        auto_save(session_id)
        return jsonify(person_to_dict(person, session))
    except ValueError:
        return jsonify({'error': '无效金额'}), 400


@app.route('/api/sessions/<session_id>/persons/<int:person_idx>/clock/<int:clock_idx>', methods=['DELETE'])
def remove_clock(session_id, person_idx, clock_idx):
    """删除卡钟费用"""
    session = get_or_create_session(session_id)
    person = session.get_person(person_idx)
    if not person:
        return jsonify({'error': '客户不存在'}), 404
    person.remove_clock_fee(clock_idx)
    auto_save(session_id)
    return jsonify(person_to_dict(person, session))


@app.route('/api/sessions/<session_id>/persons/<int:person_idx>/extra', methods=['POST'])
def add_extra(session_id, person_idx):
    """添加额外消费"""
    session = get_or_create_session(session_id)
    person = session.get_person(person_idx)
    if not person:
        return jsonify({'error': '客户不存在'}), 404
    data = request.json or {}
    name = data.get('name', '')
    try:
        price = float(data.get('price', 0))
        if not name:
            return jsonify({'error': '名称不能为空'}), 400
        if price <= 0:
            return jsonify({'error': '金额必须大于0'}), 400
        person.add_extra_item(name, price)
        auto_save(session_id)
        return jsonify(person_to_dict(person, session))
    except ValueError:
        return jsonify({'error': '无效金额'}), 400


@app.route('/api/sessions/<session_id>/persons/<int:person_idx>/extra/<int:extra_idx>', methods=['DELETE'])
def remove_extra(session_id, person_idx, extra_idx):
    """删除额外消费"""
    session = get_or_create_session(session_id)
    person = session.get_person(person_idx)
    if not person:
        return jsonify({'error': '客户不存在'}), 404
    person.remove_extra_item(extra_idx)
    auto_save(session_id)
    return jsonify(person_to_dict(person, session))


@app.route('/api/sessions/<session_id>/discount', methods=['POST'])
def set_discount(session_id):
    """设置折扣"""
    session = get_or_create_session(session_id)
    data = request.json or {}
    try:
        discount = int(data.get('discount', 75)) / 100
        if 0 < discount <= 1:
            session.discount = discount
            auto_save(session_id)
            return jsonify({'discount': session.discount})
        return jsonify({'error': '折扣必须在1-100之间'}), 400
    except ValueError:
        return jsonify({'error': '无效折扣'}), 400


@app.route('/api/sessions/<session_id>/receipt', methods=['GET'])
def get_receipt(session_id):
    """生成账单"""
    session = get_or_create_session(session_id)
    calc.session = session
    receipt = calc.generate_receipt()
    return jsonify({'receipt': receipt})


def auto_save(session_id: str):
    """自动保存"""
    if session_id in sessions:
        calc.session = sessions[session_id]
        calc.save_session(session_id)


def person_to_dict(person: Person, session: Session) -> dict:
    """Person转字典（含计算结果）"""
    return {
        'name': person.name,
        'clock_fees': person.clock_fees,
        'clock_total': person.clock_total,
        'clock_discounted': person.clock_discounted,
        'extra_items': person.extra_items,
        'extra_total': person.extra_total,
        'total': person.total,
        'discount': session.discount
    }


def session_to_dict(session: Session) -> dict:
    """Session转字典"""
    return {
        'name': session.name,
        'created_at': session.created_at,
        'discount': session.discount,
        'persons': [person_to_dict(p, session) for p in session.persons],
        'clock_total_all': session.clock_total_all,
        'clock_discounted_all': session.clock_discounted_all,
        'extra_total_all': session.extra_total_all,
        'grand_total': session.grand_total
    }


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
