"""
TRE Price Calculator - 卡钟计价软件
核心业务逻辑：卡钟75折 + 额外消费原价
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Person:
    """客户信息"""
    name: str
    clock_fees: List[float] = field(default_factory=list)  # 卡钟费用列表
    extra_items: List[dict] = field(default_factory=list)   # 额外消费 [{name, price}]

    @property
    def clock_total(self) -> float:
        """卡钟费用总和（未打折）"""
        return sum(self.clock_fees)

    @property
    def clock_discounted(self) -> float:
        """卡钟费用75折"""
        return round(self.clock_total * 0.75, 2)

    @property
    def extra_total(self) -> float:
        """额外消费总和"""
        return sum(item["price"] for item in self.extra_items)

    @property
    def total(self) -> float:
        """个人总计 = 卡钟75折 + 额外消费"""
        return round(self.clock_discounted + self.extra_total, 2)

    def add_clock_fee(self, fee: float):
        """添加卡钟费用"""
        if fee > 0:
            self.clock_fees.append(round(fee, 2))

    def remove_clock_fee(self, index: int):
        """删除指定卡钟费用"""
        if 0 <= index < len(self.clock_fees):
            self.clock_fees.pop(index)

    def add_extra_item(self, name: str, price: float):
        """添加额外消费"""
        if price > 0:
            self.extra_items.append({"name": name, "price": round(price, 2)})

    def remove_extra_item(self, index: int):
        """删除指定额外消费"""
        if 0 <= index < len(self.extra_items):
            self.extra_items.pop(index)


@dataclass
class Session:
    """计价会话"""
    name: str = ""
    created_at: str = ""
    persons: List[Person] = field(default_factory=list)
    discount: float = 0.75  # 卡钟折扣，默认75折

    @property
    def clock_total_all(self) -> float:
        """所有人卡钟总和（未打折）"""
        return sum(p.clock_total for p in self.persons)

    @property
    def clock_discounted_all(self) -> float:
        """所有人卡钟75折总和"""
        return round(self.clock_total_all * self.discount, 2)

    @property
    def extra_total_all(self) -> float:
        """所有人额外消费总和"""
        return sum(p.extra_total for p in self.persons)

    @property
    def grand_total(self) -> float:
        """总计 = 卡钟75折 + 额外消费"""
        return round(self.clock_discounted_all + self.extra_total_all, 2)

    def add_person(self, name: str) -> Person:
        """添加客户"""
        person = Person(name=name)
        self.persons.append(person)
        return person

    def remove_person(self, index: int):
        """删除客户"""
        if 0 <= index < len(self.persons):
            self.persons.pop(index)

    def get_person(self, index: int) -> Optional[Person]:
        """获取客户"""
        if 0 <= index < len(self.persons):
            return self.persons[index]
        return None

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "name": self.name,
            "created_at": self.created_at,
            "discount": self.discount,
            "persons": [asdict(p) for p in self.persons]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """从字典创建"""
        session = cls(
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            discount=data.get("discount", 0.75)
        )
        for pd in data.get("persons", []):
            person = Person(
                name=pd.get("name", ""),
                clock_fees=pd.get("clock_fees", []),
                extra_items=pd.get("extra_items", [])
            )
            session.persons.append(person)
        return session


class PriceCalculator:
    """计价器主控"""

    SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")

    def __init__(self):
        self.session: Optional[Session] = None
        os.makedirs(self.SAVE_DIR, exist_ok=True)

    def new_session(self, name: str = "") -> Session:
        """新建会话"""
        if not name:
            name = datetime.now().strftime("会话_%Y%m%d_%H%M%S")
        self.session = Session(
            name=name,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        return self.session

    def save_session(self, filename: str = "") -> str:
        """保存会话到文件，返回文件路径"""
        if not self.session:
            raise ValueError("没有活跃会话")
        if not filename:
            filename = self.session.name + ".json"
        if not filename.endswith(".json"):
            filename += ".json"
        # 清理文件名中的非法字符
        filename = "".join(c for c in filename if c.isalnum() or c in "._-中文（）() ")
        filepath = os.path.join(self.SAVE_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.session.to_dict(), f, ensure_ascii=False, indent=2)
        return filepath

    def load_session(self, filepath: str) -> Session:
        """从文件加载会话"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.session = Session.from_dict(data)
        return self.session

    def list_saves(self) -> List[dict]:
        """列出所有保存的会话"""
        saves = []
        if not os.path.exists(self.SAVE_DIR):
            return saves
        for fname in sorted(os.listdir(self.SAVE_DIR), reverse=True):
            if fname.endswith(".json"):
                filepath = os.path.join(self.SAVE_DIR, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    saves.append({
                        "filename": fname,
                        "filepath": filepath,
                        "name": data.get("name", ""),
                        "created_at": data.get("created_at", ""),
                        "person_count": len(data.get("persons", [])),
                        "grand_total": Session.from_dict(data).grand_total
                    })
                except Exception:
                    saves.append({
                        "filename": fname,
                        "filepath": filepath,
                        "name": "（损坏）",
                        "created_at": "",
                        "person_count": 0,
                        "grand_total": 0
                    })
        return saves

    def delete_save(self, filepath: str):
        """删除保存文件"""
        if os.path.exists(filepath):
            os.remove(filepath)

    def generate_receipt(self) -> str:
        """生成账单文本"""
        if not self.session:
            return "没有活跃会话"

        lines = []
        lines.append("=" * 50)
        lines.append(f"  {self.session.name}")
        lines.append(f"  {self.session.created_at}")
        lines.append("=" * 50)
        lines.append("")

        for i, p in enumerate(self.session.persons, 1):
            lines.append(f"【{p.name}】")
            if p.clock_fees:
                fee_str = " + ".join(str(f) for f in p.clock_fees)
                lines.append(f"  卡钟：{fee_str} = {p.clock_total}")
                lines.append(f"  卡钟{int(self.session.discount*100)}折：{p.clock_total} × {self.session.discount} = {p.clock_discounted}")
            if p.extra_items:
                lines.append(f"  额外消费：")
                for item in p.extra_items:
                    lines.append(f"    - {item['name']}：{item['price']}")
                lines.append(f"  额外小计：{p.extra_total}")
            lines.append(f"  >>> 个人合计：{p.total}")
            lines.append("")

        lines.append("-" * 50)
        lines.append(f"  卡钟总计（未打折）：{self.session.clock_total_all}")
        lines.append(f"  卡钟{int(self.session.discount*100)}折：{self.session.clock_discounted_all}")
        lines.append(f"  额外消费总计：{self.session.extra_total_all}")
        lines.append("=" * 50)
        lines.append(f"  ★ 总计：{self.session.grand_total} ★")
        lines.append("=" * 50)

        return "\n".join(lines)
