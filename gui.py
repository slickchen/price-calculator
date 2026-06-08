"""
TRE Price Calculator - GUI界面
基于CustomTkinter
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from calculator import PriceCalculator, Session, Person
import os


class PriceCalculatorGUI:
    """计价器GUI"""

    def __init__(self):
        self.calc = PriceCalculator()
        self.current_person_index = None

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 创建主窗口
        self.root = ctk.CTk()
        self.root.title("TRE 计价器 - 卡钟75折计算")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)

        self._create_widgets()
        self._new_session()

    def _create_widgets(self):
        """创建界面组件"""
        # 主布局：左侧人员列表，右侧详情
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== 顶部工具栏 =====
        self.toolbar = ctk.CTkFrame(self.main_frame)
        self.toolbar.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(self.toolbar, text="新建", command=self._new_session, width=80).pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar, text="保存", command=self._save_session, width=80).pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar, text="加载", command=self._load_session, width=80).pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar, text="生成账单", command=self._show_receipt, width=100).pack(side="left", padx=5)

        # 折扣设置
        ctk.CTkLabel(self.toolbar, text="卡钟折扣：").pack(side="left", padx=(20, 5))
        self.discount_var = ctk.StringVar(value="75")
        self.discount_entry = ctk.CTkEntry(self.toolbar, textvariable=self.discount_var, width=60)
        self.discount_entry.pack(side="left", padx=5)
        ctk.CTkLabel(self.toolbar, text="%").pack(side="left")
        ctk.CTkButton(self.toolbar, text="应用", command=self._apply_discount, width=60).pack(side="left", padx=5)

        # ===== 左侧：人员列表 =====
        self.left_frame = ctk.CTkFrame(self.main_frame, width=300)
        self.left_frame.pack(side="left", fill="y", padx=(0, 10))
        self.left_frame.pack_propagate(False)

        # 标题
        ctk.CTkLabel(self.left_frame, text="客户列表", font=("", 16, "bold")).pack(pady=10)

        # 添加人员
        self.add_person_frame = ctk.CTkFrame(self.left_frame)
        self.add_person_frame.pack(fill="x", padx=10, pady=5)

        self.new_person_entry = ctk.CTkEntry(self.add_person_frame, placeholder_text="输入姓名")
        self.new_person_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(self.add_person_frame, text="添加", command=self._add_person, width=60).pack(side="right")

        # 人员列表
        self.person_listbox = ctk.CTkScrollableFrame(self.left_frame)
        self.person_listbox.pack(fill="both", expand=True, padx=10, pady=5)

        # 删除人员按钮
        ctk.CTkButton(self.left_frame, text="删除选中客户", command=self._remove_person,
                      fg_color="red", hover_color="darkred").pack(pady=10)

        # ===== 右侧：详情编辑 =====
        self.right_frame = ctk.CTkFrame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True)

        # 详情标题
        self.detail_title = ctk.CTkLabel(self.right_frame, text="请选择客户", font=("", 18, "bold"))
        self.detail_title.pack(pady=10)

        # 卡钟区域
        self.clock_frame = ctk.CTkFrame(self.right_frame)
        self.clock_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(self.clock_frame, text="卡钟费用", font=("", 14, "bold")).pack(anchor="w", pady=5)

        # 添加卡钟
        self.add_clock_frame = ctk.CTkFrame(self.clock_frame)
        self.add_clock_frame.pack(fill="x", pady=5)

        self.new_clock_entry = ctk.CTkEntry(self.add_clock_frame, placeholder_text="金额", width=100)
        self.new_clock_entry.pack(side="left", padx=5)
        ctk.CTkButton(self.add_clock_frame, text="添加卡钟", command=self._add_clock_fee, width=80).pack(side="left", padx=5)

        # 卡钟列表
        self.clock_listbox = ctk.CTkScrollableFrame(self.clock_frame, height=120)
        self.clock_listbox.pack(fill="x", pady=5)

        # 卡钟小计
        self.clock_subtotal = ctk.CTkLabel(self.clock_frame, text="卡钟合计：0 | 75折：0", font=("", 12))
        self.clock_subtotal.pack(anchor="w", pady=5)

        # 额外消费区域
        self.extra_frame = ctk.CTkFrame(self.right_frame)
        self.extra_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(self.extra_frame, text="额外消费（饮品/烟酒，不打折）", font=("", 14, "bold")).pack(anchor="w", pady=5)

        # 添加额外消费
        self.add_extra_frame = ctk.CTkFrame(self.extra_frame)
        self.add_extra_frame.pack(fill="x", pady=5)

        self.new_extra_name = ctk.CTkEntry(self.add_extra_frame, placeholder_text="名称", width=120)
        self.new_extra_name.pack(side="left", padx=5)
        self.new_extra_price = ctk.CTkEntry(self.add_extra_frame, placeholder_text="金额", width=80)
        self.new_extra_price.pack(side="left", padx=5)
        ctk.CTkButton(self.add_extra_frame, text="添加", command=self._add_extra_item, width=60).pack(side="left", padx=5)

        # 额外消费列表
        self.extra_listbox = ctk.CTkScrollableFrame(self.extra_frame, height=120)
        self.extra_listbox.pack(fill="x", pady=5)

        # 额外消费小计
        self.extra_subtotal = ctk.CTkLabel(self.extra_frame, text="额外消费合计：0", font=("", 12))
        self.extra_subtotal.pack(anchor="w", pady=5)

        # ===== 底部：总计 =====
        self.total_frame = ctk.CTkFrame(self.right_frame)
        self.total_frame.pack(fill="x", padx=20, pady=20)

        self.total_label = ctk.CTkLabel(self.total_frame, text="总计：0", font=("", 20, "bold"))
        self.total_label.pack(pady=10)

    def _new_session(self):
        """新建会话"""
        self.calc.new_session()
        self._refresh_person_list()
        self._clear_detail()
        self.discount_var.set("75")

    def _save_session(self):
        """保存会话"""
        if not self.calc.session:
            return
        try:
            filepath = self.calc.save_session()
            messagebox.showinfo("保存成功", f"已保存到：\n{filepath}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _load_session(self):
        """加载会话"""
        # 创建选择窗口
        load_window = ctk.CTkToplevel(self.root)
        load_window.title("加载会话")
        load_window.geometry("600x400")
        load_window.transient(self.root)
        load_window.grab_set()

        ctk.CTkLabel(load_window, text="选择要加载的会话", font=("", 16, "bold")).pack(pady=10)

        saves_frame = ctk.CTkScrollableFrame(load_window)
        saves_frame.pack(fill="both", expand=True, padx=20, pady=10)

        saves = self.calc.list_saves()
        for save in saves:
            item_frame = ctk.CTkFrame(saves_frame)
            item_frame.pack(fill="x", pady=5)

            info_text = f"{save['name']}\n{save['created_at']} | {save['person_count']}人 | 总计：{save['grand_total']}"
            ctk.CTkLabel(item_frame, text=info_text, justify="left").pack(side="left", padx=10)

            btn_frame = ctk.CTkFrame(item_frame)
            btn_frame.pack(side="right", padx=10)

            ctk.CTkButton(btn_frame, text="加载", width=60,
                          command=lambda p=save['filepath'], w=load_window: self._do_load(p, w)).pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="删除", width=60, fg_color="red",
                          command=lambda p=save['filepath'], w=load_window: self._do_delete_save(p, w)).pack(side="left", padx=5)

        if not saves:
            ctk.CTkLabel(saves_frame, text="暂无保存记录").pack(pady=20)

    def _do_load(self, filepath: str, window):
        """执行加载"""
        try:
            self.calc.load_session(filepath)
            self.discount_var.set(str(int(self.calc.session.discount * 100)))
            self._refresh_person_list()
            self._clear_detail()
            window.destroy()
            messagebox.showinfo("加载成功", f"已加载：{self.calc.session.name}")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def _do_delete_save(self, filepath: str, window):
        """删除保存文件"""
        if messagebox.askyesno("确认删除", "确定要删除这个保存吗？"):
            self.calc.delete_save(filepath)
            window.destroy()
            self._load_session()  # 刷新列表

    def _apply_discount(self):
        """应用折扣"""
        if not self.calc.session:
            return
        try:
            discount = int(self.discount_var.get()) / 100
            if 0 < discount <= 1:
                self.calc.session.discount = discount
                self._refresh_totals()
        except ValueError:
            pass

    def _add_person(self):
        """添加客户"""
        name = self.new_person_entry.get().strip()
        if not name:
            return
        if not self.calc.session:
            self._new_session()
        self.calc.session.add_person(name)
        self.new_person_entry.delete(0, "end")
        self._refresh_person_list()

    def _remove_person(self):
        """删除客户"""
        if self.current_person_index is not None and self.calc.session:
            self.calc.session.remove_person(self.current_person_index)
            self.current_person_index = None
            self._refresh_person_list()
            self._clear_detail()

    def _refresh_person_list(self):
        """刷新人员列表"""
        # 清空列表
        for widget in self.person_listbox.winfo_children():
            widget.destroy()

        if not self.calc.session:
            return

        for i, person in enumerate(self.calc.session.persons):
            btn = ctk.CTkButton(
                self.person_listbox,
                text=f"{person.name} | {person.total}",
                command=lambda idx=i: self._select_person(idx),
                anchor="w",
                height=40
            )
            btn.pack(fill="x", pady=2)

            # 高亮选中
            if i == self.current_person_index:
                btn.configure(fg_color="green", hover_color="darkgreen")

    def _select_person(self, index: int):
        """选择客户"""
        self.current_person_index = index
        self._refresh_person_list()
        self._refresh_detail()

    def _clear_detail(self):
        """清空详情"""
        self.detail_title.configure(text="请选择客户")
        for widget in self.clock_listbox.winfo_children():
            widget.destroy()
        for widget in self.extra_listbox.winfo_children():
            widget.destroy()
        self.clock_subtotal.configure(text="卡钟合计：0 | 75折：0")
        self.extra_subtotal.configure(text="额外消费合计：0")
        self.total_label.configure(text="总计：0")

    def _refresh_detail(self):
        """刷新详情"""
        person = self.calc.session.get_person(self.current_person_index) if self.calc.session else None
        if not person:
            self._clear_detail()
            return

        self.detail_title.configure(text=f"【{person.name}】")

        # 刷新卡钟列表
        for widget in self.clock_listbox.winfo_children():
            widget.destroy()
        for i, fee in enumerate(person.clock_fees):
            item = ctk.CTkFrame(self.clock_listbox)
            item.pack(fill="x", pady=2)
            ctk.CTkLabel(item, text=f"{fee}").pack(side="left", padx=10)
            ctk.CTkButton(item, text="删除", width=60, fg_color="red",
                          command=lambda idx=i: self._remove_clock_fee(idx)).pack(side="right", padx=5)

        # 刷新额外消费列表
        for widget in self.extra_listbox.winfo_children():
            widget.destroy()
        for i, item_data in enumerate(person.extra_items):
            item = ctk.CTkFrame(self.extra_listbox)
            item.pack(fill="x", pady=2)
            ctk.CTkLabel(item, text=f"{item_data['name']}：{item_data['price']}").pack(side="left", padx=10)
            ctk.CTkButton(item, text="删除", width=60, fg_color="red",
                          command=lambda idx=i: self._remove_extra_item(idx)).pack(side="right", padx=5)

        self._refresh_totals()

    def _refresh_totals(self):
        """刷新总计"""
        person = self.calc.session.get_person(self.current_person_index) if self.calc.session else None
        if not person:
            return

        discount_pct = int(self.calc.session.discount * 100)
        self.clock_subtotal.configure(
            text=f"卡钟合计：{person.clock_total} | {discount_pct}折：{person.clock_discounted}"
        )
        self.extra_subtotal.configure(text=f"额外消费合计：{person.extra_total}")
        self.total_label.configure(text=f"总计：{self.calc.session.grand_total}")

    def _add_clock_fee(self):
        """添加卡钟费用"""
        person = self.calc.session.get_person(self.current_person_index) if self.calc.session else None
        if not person:
            messagebox.showwarning("提示", "请先选择客户")
            return
        try:
            fee = float(self.new_clock_entry.get())
            person.add_clock_fee(fee)
            self.new_clock_entry.delete(0, "end")
            self._refresh_detail()
            self._refresh_person_list()
        except ValueError:
            messagebox.showwarning("提示", "请输入有效金额")

    def _remove_clock_fee(self, index: int):
        """删除卡钟费用"""
        person = self.calc.session.get_person(self.current_person_index) if self.calc.session else None
        if person:
            person.remove_clock_fee(index)
            self._refresh_detail()
            self._refresh_person_list()

    def _add_extra_item(self):
        """添加额外消费"""
        person = self.calc.session.get_person(self.current_person_index) if self.calc.session else None
        if not person:
            messagebox.showwarning("提示", "请先选择客户")
            return
        name = self.new_extra_name.get().strip()
        try:
            price = float(self.new_extra_price.get())
            if not name:
                messagebox.showwarning("提示", "请输入消费名称")
                return
            person.add_extra_item(name, price)
            self.new_extra_name.delete(0, "end")
            self.new_extra_price.delete(0, "end")
            self._refresh_detail()
            self._refresh_person_list()
        except ValueError:
            messagebox.showwarning("提示", "请输入有效金额")

    def _remove_extra_item(self, index: int):
        """删除额外消费"""
        person = self.calc.session.get_person(self.current_person_index) if self.calc.session else None
        if person:
            person.remove_extra_item(index)
            self._refresh_detail()
            self._refresh_person_list()

    def _show_receipt(self):
        """显示账单"""
        if not self.calc.session or not self.calc.session.persons:
            messagebox.showwarning("提示", "暂无数据")
            return

        receipt = self.calc.generate_receipt()

        # 创建账单窗口
        receipt_window = ctk.CTkToplevel(self.root)
        receipt_window.title("账单")
        receipt_window.geometry("500x600")

        text = ctk.CTkTextbox(receipt_window, font=("Courier", 12))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("0.0", receipt)
        text.configure(state="disabled")

        ctk.CTkButton(receipt_window, text="复制到剪贴板",
                      command=lambda: self._copy_receipt(receipt_window, receipt)).pack(pady=10)

    def _copy_receipt(self, window, text: str):
        """复制账单到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("已复制", "账单已复制到剪贴板")

    def run(self):
        """运行GUI"""
        self.root.mainloop()


if __name__ == "__main__":
    app = PriceCalculatorGUI()
    app.run()
