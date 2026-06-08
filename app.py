"""
TRE Price Calculator - Web版 v3
Flask + SQLite + 实时同步 + 快照备份
支持：自定义折扣、重置恢复、手动保存快照
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import json
import uuid
import os
from datetime import datetime

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            discount REAL NOT NULL DEFAULT 0.75,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS clock_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            fee REAL NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS extra_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT ''
        );
    """)
    db.commit()
    db.close()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_session_dict(db, session):
    s = dict(session)
    persons = db.execute(
        "SELECT * FROM persons WHERE session_id=? ORDER BY sort_order, id", (s['id'],)
    ).fetchall()

    s['persons'] = []
    s['clock_total_all'] = 0
    s['clock_discounted_all'] = 0
    s['extra_total_all'] = 0

    for p in persons:
        pd = dict(p)
        clocks = db.execute(
            "SELECT * FROM clock_fees WHERE person_id=? ORDER BY sort_order, id", (pd['id'],)
        ).fetchall()
        extras = db.execute(
            "SELECT * FROM extra_items WHERE person_id=? ORDER BY sort_order, id", (pd['id'],)
        ).fetchall()

        pd['clock_fees'] = [dict(c) for c in clocks]
        pd['extra_items'] = [dict(e) for e in extras]
        pd['clock_total'] = sum(c['fee'] for c in clocks)
        pd['clock_discounted'] = round(pd['clock_total'] * s['discount'], 2)
        pd['extra_total'] = sum(e['price'] for e in extras)
        pd['total'] = round(pd['clock_discounted'] + pd['extra_total'], 2)

        s['clock_total_all'] += pd['clock_total']
        s['clock_discounted_all'] += pd['clock_discounted']
        s['extra_total_all'] += pd['extra_total']
        s['persons'].append(pd)

    s['clock_total_all'] = round(s['clock_total_all'], 2)
    s['clock_discounted_all'] = round(s['clock_discounted_all'], 2)
    s['extra_total_all'] = round(s['extra_total_all'], 2)
    s['grand_total'] = round(s['clock_discounted_all'] + s['extra_total_all'], 2)

    # 检查有无备份可恢复
    backup = db.execute(
        "SELECT * FROM snapshots WHERE session_id=? AND label='__reset_backup__' ORDER BY created_at DESC LIMIT 1",
        (s['id'],)
    ).fetchone()
    s['has_backup'] = backup is not None

    return s


def session_to_json(db, session_id):
    """将会话完整数据导出为JSON（用于快照）"""
    session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        return {}
    s = dict(session)
    persons = db.execute(
        "SELECT * FROM persons WHERE session_id=? ORDER BY sort_order, id", (session_id,)
    ).fetchall()
    result = {
        'name': s['name'],
        'discount': s['discount'],
        'created_at': s['created_at'],
        'persons': []
    }
    for p in persons:
        pd = dict(p)
        clocks = db.execute(
            "SELECT * FROM clock_fees WHERE person_id=? ORDER BY sort_order, id", (pd['id'],)
        ).fetchall()
        extras = db.execute(
            "SELECT * FROM extra_items WHERE person_id=? ORDER BY sort_order, id", (pd['id'],)
        ).fetchall()
        result['persons'].append({
            'name': pd['name'],
            'clock_fees': [c['fee'] for c in clocks],
            'extra_items': [{'name': e['name'], 'price': e['price']} for e in extras]
        })
    return result


def restore_from_json(db, session_id, data):
    """从快照JSON恢复数据到会话"""
    # 先清空现有数据
    db.execute("DELETE FROM clock_fees WHERE person_id IN (SELECT id FROM persons WHERE session_id=?)", (session_id,))
    db.execute("DELETE FROM extra_items WHERE person_id IN (SELECT id FROM persons WHERE session_id=?)", (session_id,))
    db.execute("DELETE FROM persons WHERE session_id=?", (session_id,))

    # 恢复折扣
    if 'discount' in data:
        db.execute("UPDATE sessions SET discount=? WHERE id=?", (data['discount'], session_id))

    # 恢复客户
    for i, pd in enumerate(data.get('persons', [])):
        db.execute("INSERT INTO persons (session_id, name, sort_order) VALUES (?,?,?)",
                   (session_id, pd['name'], i))
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for j, fee in enumerate(pd.get('clock_fees', [])):
            db.execute("INSERT INTO clock_fees (person_id, fee, sort_order) VALUES (?,?,?)",
                       (pid, fee, j))
        for j, extra in enumerate(pd.get('extra_items', [])):
            db.execute("INSERT INTO extra_items (person_id, name, price, sort_order) VALUES (?,?,?,?)",
                       (pid, extra['name'], extra['price'], j))

    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), session_id))
    db.commit()


def generate_receipt(session_data):
    s = session_data
    lines = []
    lines.append("=" * 50)
    lines.append(f"  {s['name']}")
    lines.append(f"  {s['created_at']}")
    lines.append("=" * 50)
    lines.append("")

    for p in s['persons']:
        lines.append(f"【{p['name']}】")
        if p['clock_fees']:
            fee_str = " + ".join(str(c['fee']) for c in p['clock_fees'])
            lines.append(f"  卡钟：{fee_str} = {p['clock_total']}")
            discount_pct = int(s['discount'] * 100)
            lines.append(f"  卡钟{discount_pct}%折：{p['clock_total']} × {s['discount']} = {p['clock_discounted']}")
        if p['extra_items']:
            lines.append(f"  额外消费：")
            for e in p['extra_items']:
                lines.append(f"    - {e['name']}：{e['price']}")
            lines.append(f"  额外小计：{p['extra_total']}")
        lines.append(f"  >>> 个人合计：{p['total']}")
        lines.append("")

    discount_pct = int(s['discount'] * 100)
    lines.append("-" * 50)
    lines.append(f"  卡钟总计（未打折）：{s['clock_total_all']}")
    lines.append(f"  卡钟{discount_pct}%折：{s['clock_discounted_all']}")
    lines.append(f"  额外消费总计：{s['extra_total_all']}")
    lines.append("=" * 50)
    lines.append(f"  ★ 总计：{s['grand_total']} ★")
    lines.append("=" * 50)
    return "\n".join(lines)


# ============ 路由 ============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    db = get_db()
    rows = db.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    result = []
    for r in rows:
        s = build_session_dict(db, r)
        result.append({
            'id': s['id'],
            'name': s['name'],
            'created_at': s['created_at'],
            'updated_at': s['updated_at'],
            'person_count': len(s['persons']),
            'grand_total': s['grand_total']
        })
    db.close()
    return jsonify(result)


@app.route('/api/sessions', methods=['POST'])
def create_session():
    data = request.json or {}
    name = data.get('name', '')
    if not name:
        name = datetime.now().strftime("会话_%Y%m%d_%H%M%S")
    sid = str(uuid.uuid4())[:8]
    ts = now_str()
    db = get_db()
    db.execute("INSERT INTO sessions (id, name, created_at, updated_at) VALUES (?,?,?,?)",
               (sid, name, ts, ts))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>', methods=['GET'])
def get_session(sid):
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not session:
        db.close()
        return jsonify({'error': '会话不存在'}), 404
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>', methods=['DELETE'])
def delete_session(sid):
    db = get_db()
    db.execute("DELETE FROM snapshots WHERE session_id=?", (sid,))
    db.execute("DELETE FROM sessions WHERE id=?", (sid,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


# --- 折扣 ---

@app.route('/api/sessions/<sid>/discount', methods=['POST'])
def set_discount(sid):
    data = request.json or {}
    try:
        discount = int(data.get('discount', 75)) / 100
        if not (0 < discount <= 1):
            return jsonify({'error': '折扣必须在1-100之间'}), 400
    except ValueError:
        return jsonify({'error': '无效折扣'}), 400
    db = get_db()
    db.execute("UPDATE sessions SET discount=?, updated_at=? WHERE id=?", (discount, now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


# --- 重置（自动备份） ---

@app.route('/api/sessions/<sid>/reset', methods=['POST'])
def reset_session(sid):
    """重置会话：自动备份当前数据，然后清空"""
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not session:
        db.close()
        return jsonify({'error': '会话不存在'}), 404

    # 自动备份当前数据
    snapshot_data = session_to_json(db, sid)
    if snapshot_data.get('persons'):
        db.execute(
            "INSERT INTO snapshots (session_id, label, data, created_at) VALUES (?,?,?,?)",
            (sid, '__reset_backup__', json.dumps(snapshot_data, ensure_ascii=False), now_str())
        )

    # 清空数据
    db.execute("DELETE FROM clock_fees WHERE person_id IN (SELECT id FROM persons WHERE session_id=?)", (sid,))
    db.execute("DELETE FROM extra_items WHERE person_id IN (SELECT id FROM persons WHERE session_id=?)", (sid,))
    db.execute("DELETE FROM persons WHERE session_id=?", (sid,))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


# --- 恢复最近备份 ---

@app.route('/api/sessions/<sid>/restore', methods=['POST'])
def restore_session(sid):
    """恢复最近一次重置前的数据"""
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not session:
        db.close()
        return jsonify({'error': '会话不存在'}), 404

    backup = db.execute(
        "SELECT * FROM snapshots WHERE session_id=? AND label='__reset_backup__' ORDER BY created_at DESC LIMIT 1",
        (sid,)
    ).fetchone()
    if not backup:
        db.close()
        return jsonify({'error': '没有可恢复的备份'}), 404

    data = json.loads(backup['data'])
    restore_from_json(db, sid, data)

    # 删除已恢复的备份
    db.execute("DELETE FROM snapshots WHERE id=?", (backup['id'],))
    db.commit()

    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


# --- 手动保存快照 ---

@app.route('/api/sessions/<sid>/snapshots', methods=['GET'])
def list_snapshots(sid):
    """列出会话的所有快照"""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM snapshots WHERE session_id=? AND label!='__reset_backup__' ORDER BY created_at DESC",
        (sid,)
    ).fetchall()
    result = []
    for r in rows:
        rd = dict(r)
        data = json.loads(rd['data'])
        result.append({
            'id': rd['id'],
            'label': rd['label'],
            'created_at': rd['created_at'],
            'person_count': len(data.get('persons', [])),
            'grand_total': _calc_grand_total(data)
        })
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>/snapshots', methods=['POST'])
def save_snapshot(sid):
    """手动保存快照"""
    data = request.json or {}
    label = data.get('label', '').strip()
    if not label:
        label = now_str()
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not session:
        db.close()
        return jsonify({'error': '会话不存在'}), 404

    snapshot_data = session_to_json(db, sid)
    db.execute(
        "INSERT INTO snapshots (session_id, label, data, created_at) VALUES (?,?,?,?)",
        (sid, label, json.dumps(snapshot_data, ensure_ascii=False), now_str())
    )
    db.commit()
    db.close()
    return jsonify({'ok': True, 'label': label})


@app.route('/api/sessions/<sid>/snapshots/<int:snap_id>', methods=['GET'])
def get_snapshot(sid, snap_id):
    """获取快照详情"""
    db = get_db()
    snap = db.execute(
        "SELECT * FROM snapshots WHERE id=? AND session_id=?", (snap_id, sid)
    ).fetchone()
    if not snap:
        db.close()
        return jsonify({'error': '快照不存在'}), 404
    data = json.loads(snap['data'])
    db.close()
    return jsonify({
        'id': snap['id'],
        'label': snap['label'],
        'created_at': snap['created_at'],
        'data': data
    })


@app.route('/api/sessions/<sid>/snapshots/<int:snap_id>/restore', methods=['POST'])
def restore_snapshot(sid, snap_id):
    """从快照恢复"""
    db = get_db()
    snap = db.execute(
        "SELECT * FROM snapshots WHERE id=? AND session_id=?", (snap_id, sid)
    ).fetchone()
    if not snap:
        db.close()
        return jsonify({'error': '快照不存在'}), 404

    data = json.loads(snap['data'])
    restore_from_json(db, sid, data)

    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>/snapshots/<int:snap_id>', methods=['DELETE'])
def delete_snapshot(sid, snap_id):
    """删除快照"""
    db = get_db()
    db.execute("DELETE FROM snapshots WHERE id=? AND session_id=?", (snap_id, sid))
    db.commit()
    db.close()
    return jsonify({'ok': True})


def _calc_grand_total(data):
    """从快照数据计算总计"""
    discount = data.get('discount', 0.75)
    total = 0
    for p in data.get('persons', []):
        clock_total = sum(p.get('clock_fees', []))
        clock_discounted = round(clock_total * discount, 2)
        extra_total = sum(e['price'] for e in p.get('extra_items', []))
        total += clock_discounted + extra_total
    return round(total, 2)


# --- 客户 ---

@app.route('/api/sessions/<sid>/persons', methods=['POST'])
def add_person(sid):
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '姓名不能为空'}), 400
    db = get_db()
    max_order = db.execute("SELECT COALESCE(MAX(sort_order),0) FROM persons WHERE session_id=?", (sid,)).fetchone()[0]
    db.execute("INSERT INTO persons (session_id, name, sort_order) VALUES (?,?,?)",
               (sid, name, max_order + 1))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>/persons/<int:pid>', methods=['DELETE'])
def remove_person(sid, pid):
    db = get_db()
    db.execute("DELETE FROM persons WHERE id=? AND session_id=?", (pid, sid))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


# --- 卡钟 ---

@app.route('/api/sessions/<sid>/persons/<int:pid>/clock', methods=['POST'])
def add_clock(sid, pid):
    data = request.json or {}
    try:
        fee = float(data.get('fee', 0))
        if fee <= 0:
            return jsonify({'error': '金额必须大于0'}), 400
    except ValueError:
        return jsonify({'error': '无效金额'}), 400
    db = get_db()
    person = db.execute("SELECT * FROM persons WHERE id=? AND session_id=?", (pid, sid)).fetchone()
    if not person:
        db.close()
        return jsonify({'error': '客户不存在'}), 404
    max_order = db.execute("SELECT COALESCE(MAX(sort_order),0) FROM clock_fees WHERE person_id=?", (pid,)).fetchone()[0]
    db.execute("INSERT INTO clock_fees (person_id, fee, sort_order) VALUES (?,?,?)",
               (pid, fee, max_order + 1))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>/persons/<int:pid>/clock/<int:cid>', methods=['DELETE'])
def remove_clock(sid, pid, cid):
    db = get_db()
    db.execute("DELETE FROM clock_fees WHERE id=? AND person_id=?", (cid, pid))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


# --- 额外消费 ---

@app.route('/api/sessions/<sid>/persons/<int:pid>/extra', methods=['POST'])
def add_extra(sid, pid):
    data = request.json or {}
    name = data.get('name', '').strip()
    try:
        price = float(data.get('price', 0))
        if not name:
            return jsonify({'error': '名称不能为空'}), 400
        if price <= 0:
            return jsonify({'error': '金额必须大于0'}), 400
    except ValueError:
        return jsonify({'error': '无效金额'}), 400
    db = get_db()
    person = db.execute("SELECT * FROM persons WHERE id=? AND session_id=?", (pid, sid)).fetchone()
    if not person:
        db.close()
        return jsonify({'error': '客户不存在'}), 404
    max_order = db.execute("SELECT COALESCE(MAX(sort_order),0) FROM extra_items WHERE person_id=?", (pid,)).fetchone()[0]
    db.execute("INSERT INTO extra_items (person_id, name, price, sort_order) VALUES (?,?,?,?)",
               (pid, name, price, max_order + 1))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


@app.route('/api/sessions/<sid>/persons/<int:pid>/extra/<int:eid>', methods=['DELETE'])
def remove_extra(sid, pid, eid):
    db = get_db()
    db.execute("DELETE FROM extra_items WHERE id=? AND person_id=?", (eid, pid))
    db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now_str(), sid))
    db.commit()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    result = build_session_dict(db, session)
    db.close()
    return jsonify(result)


# --- 账单 ---

@app.route('/api/sessions/<sid>/receipt', methods=['GET'])
def get_receipt(sid):
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not session:
        db.close()
        return jsonify({'error': '会话不存在'}), 404
    s = build_session_dict(db, session)
    db.close()
    return jsonify({'receipt': generate_receipt(s)})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
