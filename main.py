import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.window import Window
import requests
import json
import os

Window.softinput_mode = "below_target"

# ========== 数据获取（用东方财富接口，避免 akshare 依赖太重） ==========
def fetch_sme_market():
    """直接调用东方财富接口，获取中小板（002开头）实时行情"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": 5000, "po": 1, "np": 1,
        "fltt": 2, "invt": 2, "fid": "f20",  # f20 = 总市值，升序
        "fs": "m:0+t:13",  # 中小板
        "fields": "f12,f14,f2,f20",  # 代码,名称,最新价,总市值
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    data = r.json()
    items = data["data"]["diff"]
    rows = []
    for it in items:
        code = it.get("f12", "")
        name = it.get("f14", "")
        price = it.get("f2", 0)
        cap = it.get("f20", 0)
        if not code.startswith("002"):
            continue
        if "ST" in name:
            continue
        if price in ("-", 0, None):
            continue
        if cap in ("-", 0, None):
            continue
        rows.append({"代码": code, "名称": name, "最新价": float(price), "总市值": float(cap)})
    rows.sort(key=lambda x: x["总市值"])
    return rows

# ========== 策略 ==========
def calc_signals(holdings, market):
    if len(market) < 35:
        return None, None, "市场数据不足"
    threshold = market[34]["总市值"]
    code_map = {s["代码"]: s for s in market}
    
    sell = []
    for code in holdings:
        s = code_map.get(code)
        if s and s["总市值"] > threshold:
            sell.append(s)
    
    top30 = market[:30]
    available = [s for s in top30 if s["代码"] not in holdings]
    buy = available[:len(sell)]
    
    return {"sell": sell, "buy": buy, "threshold": threshold}, code_map, None

# ========== 持仓存储 ==========
def get_storage_path():
    try:
        from android.storage import app_storage_path
        base = app_storage_path()
    except Exception:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "holdings.json")

def load_holdings():
    p = get_storage_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f).get("codes", [])
        except Exception:
            return []
    return []

def save_holdings(codes):
    p = get_storage_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"codes": codes}, f, ensure_ascii=False, indent=2)

# ========== UI ==========
class StrategyApp(App):
    def build(self):
        self.title = "中小板小市值策略"
        root = BoxLayout(orientation="vertical", padding=10, spacing=8)
        
        root.add_widget(Label(
            text="[b]中小板小市值轮动策略[/b]",
            markup=True, size_hint_y=None, height=40, font_size=20
        ))
        
        root.add_widget(Label(
            text="输入持仓代码（用逗号或空格分隔，如 002001,002002）：",
            size_hint_y=None, height=30, font_size=13
        ))
        
        self.input = TextInput(
            text=",".join(load_holdings()),
            size_hint_y=None, height=100, multiline=True, font_size=16
        )
        root.add_widget(self.input)
        
        btns = BoxLayout(size_hint_y=None, height=50, spacing=8)
        self.btn_run = Button(text="计算买卖信号", font_size=16, background_color=(0.2, 0.6, 1, 1))
        self.btn_run.bind(on_press=self.on_run)
        btns.add_widget(self.btn_run)
        
        btn_save = Button(text="保存持仓", font_size=16, background_color=(0.2, 0.8, 0.4, 1))
        btn_save.bind(on_press=self.on_save)
        btns.add_widget(btn_save)
        root.add_widget(btns)
        
        self.status = Label(text="就绪", size_hint_y=None, height=30, font_size=13, color=(0.5, 0.5, 0.5, 1))
        root.add_widget(self.status)
        
        sv = ScrollView()
        self.result = Label(
            text="点击 [计算买卖信号] 开始分析",
            size_hint_y=None, halign="left", valign="top",
            markup=True, font_size=14, padding=(10, 10)
        )
        self.result.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1]))
        self.result.bind(width=lambda inst, val: setattr(inst, "text_size", (val - 20, None)))
        sv.add_widget(self.result)
        root.add_widget(sv)
        
        return root
    
    def parse_holdings(self):
        text = self.input.text.replace("，", ",").replace(" ", ",").replace("\n", ",")
        codes = [c.strip() for c in text.split(",") if c.strip()]
        return list(dict.fromkeys(codes))  # 去重保序
    
    def on_save(self, *_):
        codes = self.parse_holdings()
        save_holdings(codes)
        self.status.text = f"已保存 {len(codes)} 只持仓"
    
    def on_run(self, *_):
        self.btn_run.disabled = True
        self.status.text = "正在获取行情数据..."
        self.result.text = "加载中，请稍候..."
        threading.Thread(target=self._run_task, daemon=True).start()
    
    def _run_task(self):
        try:
            holdings = self.parse_holdings()
            market = fetch_sme_market()
            sig, cmap, err = calc_signals(holdings, market)
            if err:
                Clock.schedule_once(lambda dt: self._show_error(err))
                return
            Clock.schedule_once(lambda dt: self._show_result(holdings, market, sig, cmap))
        except Exception as e:
            msg = str(e)
            Clock.schedule_once(lambda dt: self._show_error(msg))
    
    def _show_error(self, msg):
        self.btn_run.disabled = False
        self.status.text = "出错"
        self.result.text = f"[color=ff3333]错误：{msg}[/color]"
    
    def _show_result(self, holdings, market, sig, cmap):
        self.btn_run.disabled = False
        self.status.text = f"完成 | 中小板{len(market)}只 | 持仓{len(holdings)}只"
        
        lines = []
        lines.append(f"[b]卖出阈值（倒数第35名市值）：[color=ff8800]{sig['threshold']/1e8:.2f} 亿[/color][/b]\n")
        
        # 持仓现状
        lines.append("[b]【当前持仓】[/b]")
        if not holdings:
            lines.append("  （无）")
        else:
            for c in holdings:
                s = cmap.get(c)
                if s:
                    flag = " [color=ff3333]★超阈值[/color]" if s["总市值"] > sig["threshold"] else ""
                    lines.append(f"  {c} {s['名称']}  {s['总市值']/1e8:.2f}亿{flag}")
                else:
                    lines.append(f"  {c}  [color=999999](未找到)[/color]")
        
        # 卖出
        lines.append(f"\n[b][color=ff3333]【卖出建议】{len(sig['sell'])}只[/color][/b]")
        if sig["sell"]:
            for s in sig["sell"]:
                lines.append(f"  💸 {s['代码']} {s['名称']}  市值 {s['总市值']/1e8:.2f}亿  价 {s['最新价']}")
        else:
            lines.append("  ✅ 无需卖出")
        
        # 买入
        lines.append(f"\n[b][color=00aa00]【买入建议】{len(sig['buy'])}只[/color][/b]")
        if sig["buy"]:
            for s in sig["buy"]:
                lines.append(f"  🛒 {s['代码']} {s['名称']}  市值 {s['总市值']/1e8:.2f}亿  价 {s['最新价']}")
        else:
            lines.append("  无需买入")
        
        # Top30 参考
        lines.append("\n[b]【市值最小 Top30 候选池】[/b]")
        for i, s in enumerate(market[:30], 1):
            mark = " [color=00aa00]●持仓[/color]" if s["代码"] in holdings else ""
            lines.append(f"  {i:2d}. {s['代码']} {s['名称']}  {s['总市值']/1e8:.2f}亿{mark}")
        
        self.result.text = "\n".join(lines)


if __name__ == "__main__":
    StrategyApp().run()
