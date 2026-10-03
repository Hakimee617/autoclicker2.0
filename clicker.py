import ctypes
import ctypes.wintypes as wt
import math
import queue
import random
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageDraw, ImageTk  # type: ignore
    HAS_PIL = True
except Exception:                                    
    HAS_PIL = False


#Win32 API 封装
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# 这是一只初音 你会朝她哈气吗
# * _______________#########_______________________
# * ______________############_____________________
# * ______________#############____________________
# * _____________##__###########___________________
# * ____________###__######_#####__________________
# * ____________###_#######___####_________________
# * ___________###__##########_####________________
# * __________####__###########_####_______________
# * _________#####___###########__#####_____________
# * _______######___###_########___#####___________
# * _______#####___###___########___######_________
# * ______######___###__###########___######_______
# * _____######___####_##############__######______
# * ____#######__#####################_#######_____
# * ____#######__##############################____
# * ___#######__######_#################_#######___
# * ___#######__######_######_#########___######___
# * ___#######____##__######___######_____######___
# * ___#######________######____#####_____#####____
# * ____######________#####_____#####_____####_____
# * _____#####________####______#####_____###______
# * ______#####______;###________###______#________
# * ________##_______####________####______________

# 鼠标事件标志
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# 虚拟键码
VK_LBUTTON = 0x01
VK_PRIOR = 0x21           
VK_NEXT = 0x22   
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

# 鼠标窗口消息
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010

PICK_TIMEOUT = 60               # 拾取位置超时（秒）
START_HOTKEY = 'Ctrl+Alt+PageUp'    # 全局开始快捷键
STOP_HOTKEY = 'Ctrl+Alt+PageDown'   # 全局紧急终止快捷键

BUTTON_EVENTS = {
    'left': (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    'right': (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    'middle': (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

BUTTON_MSG = {
    'left': (WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON),
    'right': (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON),
    'middle': (WM_MBUTTONDOWN, WM_MBUTTONUP, MK_MBUTTON),
}


def enum_visible_windows():
    """枚举所有带标题且可见的顶层窗口，返回 [(hwnd, title), ...]"""
    results = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if title:
            results.append((hwnd, title))
        return True

    user32.EnumWindows(callback, 0)
    results.sort(key=lambda item: item[1].lower())
    return results


def get_window_rect(hwnd):
    """获取窗口在屏幕上的矩形 (left, top, right, bottom)"""
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def is_window_valid(hwnd):
    """窗口句柄是否仍然有效可见"""
    return bool(hwnd) and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd)


def get_window_title(hwnd):
    """实时读取窗口标题（标题会变，不能当成身份用）"""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ''
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()


def get_cursor_pos():
    """获取当前鼠标屏幕坐标 (x, y)"""
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def screen_to_client(hwnd, x, y):
    """屏幕坐标 -> 客户区坐标（正确处理标题栏等非客户区）"""
    pt = wt.POINT(int(x), int(y))
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def inject_click(hwnd, x, y, button, duration, is_hold, interval, stop_event):
    """后台注入点击：向目标窗口直接发送鼠标消息，不移动物理鼠标。"""
    cx, cy = screen_to_client(hwnd, x, y)
    lparam = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
    down, up, mk = BUTTON_MSG[button]

    user32.PostMessageW(hwnd, down, mk, lparam)
    if is_hold:
        end = time.time() + duration
        while time.time() < end:
            if stop_event.is_set():
                break
            time.sleep(0.01)
    else:
        time.sleep(0.005)
        if stop_event.is_set():
            time.sleep(0.005)
    user32.PostMessageW(hwnd, up, 0, lparam)
    time.sleep(max(0.0, interval))


def click_at(x, y, button, duration, is_hold, interval, stop_event):
    """在 (x, y) 处执行一次物理点击。"""
    down_flag, up_flag = BUTTON_EVENTS[button]
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.03)
    user32.mouse_event(down_flag, 0, 0, 0, 0)

    if is_hold:
        end = time.time() + duration
        while time.time() < end:
            if stop_event.is_set():
                break
            time.sleep(0.01)
    else:
        time.sleep(0.03)
        if stop_event.is_set():
            time.sleep(0.01)

    user32.mouse_event(up_flag, 0, 0, 0, 0)
    time.sleep(max(0.0, interval))

#  界面底层：配色 / 圆角绘制 / 动画控件
class T:
    """统一色板"""
    BG       = '#0f0f16'   
    CARD     = '#191922'   
    FIELD    = '#232330'   
    FIELD_HI = '#2c2c3b'
    LINE     = '#2b2b39'   
    TEXT     = '#e9e9f4'
    MUTED    = '#8a8aa2'
    ACCENT   = '#5b8cff'   
    GREEN    = '#33c98b'
    RED      = '#ef5f6b'
    DISABLED = '#242430'


FONT = 'Microsoft YaHei UI'
_TICK = 16         
_IMG_CACHE = {}


def mix(c1, c2, t):
    """两色线性插值，t=0 取 c1"""
    t = max(0.0, min(1.0, t))
    c1 = c1.lstrip('#'); c2 = c2.lstrip('#')
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    return '#%02x%02x%02x' % (
        int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t))


def _round_points(x1, y1, x2, y2, r):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def _round_image(w, h, r, fill, bg, outline=None, ow=1, ss=3):
    key = (w, h, r, fill, bg, outline, ow)
    photo = _IMG_CACHE.get(key)
    if photo is not None:
        return photo
    if len(_IMG_CACHE) > 260:
        _IMG_CACHE.clear()
    big = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle(
        [0, 0, w * ss - 1, h * ss - 1], radius=max(1, int(r * ss)), fill=fill,
        outline=outline, width=max(1, int(ow * ss)) if outline else 0)
    big = big.resize((w, h), Image.LANCZOS)
    base = Image.new('RGB', (w, h), bg)
    base.paste(big, (0, 0), big)
    photo = ImageTk.PhotoImage(base)
    _IMG_CACHE[key] = photo
    return photo


def paint_round(cv, x1, y1, x2, y2, r, fill, bg, outline=None, ow=1, tags=()):
    """在 Canvas 上画一个抗锯齿圆角矩形（PIL 不可用时退化为平滑多边形）"""
    w, h = int(round(x2 - x1)), int(round(y2 - y1))
    if w < 2 or h < 2:
        return None
    if HAS_PIL:
        photo = _round_image(w, h, r, fill, bg, outline, ow)
        refs = getattr(cv, '_img_refs', None)
        if refs is not None:
            refs.append(photo)
        return cv.create_image(x1, y1, anchor='nw', image=photo, tags=tags)
    return cv.create_polygon(_points(x1, y1, x2, y2, r), smooth=True, fill=fill,
                             outline=outline or '', width=ow if outline else 0, tags=tags)


def _points(x1, y1, x2, y2, r):       
    return _round_points(x1, y1, x2, y2, r)


def round_window(win, w, h, r):
    """把顶层窗口裁成圆角"""
    try:
        hwnd = user32.GetAncestor(win.winfo_id(), 2)  # GA_ROOT
        rgn = gdi32.CreateRoundRectRgn(0, 0, int(w) + 1, int(h) + 1, r * 2, r * 2)
        user32.SetWindowRgn(hwnd, rgn, True)
    except Exception:
        pass


class _Base(tk.Canvas):
    """带 16ms 缓动的小工具基类"""

    def __init__(self, master, surface, **kw):
        super().__init__(master, bg=surface, highlightthickness=0, bd=0,
                         takefocus=0, **kw)
        self._surface = surface
        self._img_refs = []
        self._cw = int(kw.get('width', 10))
        self._ch = int(kw.get('height', 10))
        self._ease = 0.0          # 当前动画进度 0~1
        self._ease_target = 0.0
        self._job = None
        self.bind('<Configure>', self._on_configure)

    def _on_configure(self, event):
        if event.width != self._cw or event.height != self._ch:
            self._cw, self._ch = event.width, event.height
            self.render()

    def ease_to(self, target):
        self._ease_target = float(target)
        if self._job is None:
            self._job = self.after(_TICK, self._ease_tick)

    def _ease_tick(self):
        self._job = None
        d = self._ease_target - self._ease
        if abs(d) < 0.015:
            self._ease = self._ease_target
            self.render()
            return
        self._ease += d * 0.32
        self.render()
        self._job = self.after(_TICK, self._ease_tick)

    def render(self):
        raise NotImplementedError


#圆角按钮
class RoundedButton(_Base):
    """统一按钮： primary / success / danger / soft / ghost"""

    def __init__(self, master, text='', command=None, kind='primary', width=120,
                 height=34, radius=11, surface=T.CARD, font=None, enabled=True, pad=14):
        super().__init__(master, surface, width=width, height=height)
        self._text = text
        self._command = command
        self._kind = kind
        self._radius = radius
        self._font = font or (FONT, 9, 'bold')
        self._pad = pad
        self.enabled = enabled
        self._pressed = False
        self._hover = 0.0
        self.configure(cursor='hand2' if enabled else 'arrow')
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.after(0, self.render)

    #颜色
    def _colors(self):
        k = self._kind
        hover = self._hover
        if not self.enabled:
            fill = self._surface if k == 'ghost' else T.DISABLED
            return fill, T.MUTED
        if k == 'ghost':
            fill = mix(self._surface, '#ffffff', 0.08 * hover)
            fg = mix(T.MUTED, T.TEXT, hover)
            if self._pressed:
                fill = mix(fill, '#000000', 0.25)
            return fill, fg
        base = {'primary': T.ACCENT, 'success': T.GREEN,
                'danger': T.RED, 'soft': T.FIELD}[k]
        fill = mix(base, '#ffffff', 0.15 * hover)
        if self._pressed:
            fill = mix(fill, '#000000', 0.16)
        return fill, '#ffffff'

    def render(self):
        self.delete('all')
        self._img_refs.clear()
        w, h = max(self._cw, 8), max(self._ch, 8)
        fill, fg = self._colors()
        paint_round(self, 0, 0, w, h, self._radius, fill, self._surface)
        dy = 1 if self._pressed else 0
        self.create_text(w / 2, h / 2 + dy, text=self._text, fill=fg, font=self._font)

    #事件
    def _on_enter(self, _):
        if self.enabled:
            self.ease_to(1)

    def _on_leave(self, _):
        self._pressed = False
        self.ease_to(0)

    def _on_press(self, _):
        if self.enabled:
            self._pressed = True
            self.render()

    def _on_release(self, _):
        if not self.enabled:
            return
        was = self._pressed
        self._pressed = False
        self.render()
        if was and self._command:
            self._command()

    #对外接口
    def configure(self, cnf=None, **kw):
        state = kw.pop('state', None)
        text = kw.pop('text', None)
        if state is not None:
            self.enabled = (state == 'normal')
            try:
                tk.Canvas.configure(self, cursor='hand2' if self.enabled else 'arrow')
            except tk.TclError:
                pass
        if text is not None:
            self._text = text
        if cnf or kw:
            try:
                tk.Canvas.configure(self, cnf or {}, **kw)
            except tk.TclError:
                pass
        self.render()

    config = configure


#分段选择器
class Segmented(_Base):
    """整条轨道 + 滑动的指示块，替代原来的单选圆点"""

    def __init__(self, master, options, variable, command=None, surface=T.CARD,
                 height=32, radius=10, font=None):
        super().__init__(master, surface, width=200, height=height)
        self._opts = list(options)          # [(文本, 值), ...]
        self.variable = variable
        self._command = command
        self._radius = radius
        self._font = font or (FONT, 9)
        self._pos = self._index_of(variable.get())
        self._ease = self._pos
        self._ease_target = self._pos
        self.configure(cursor='hand2')
        self.bind('<ButtonPress-1>', self._on_click)
        self.after(0, self.render)

    def _index_of(self, value):
        for i, (_, v) in enumerate(self._opts):
            if v == value:
                return float(i)
        return 0.0

    def render(self):
        self.delete('all')
        self._img_refs.clear()
        w, h = max(self._cw, 8), max(self._ch, 8)
        r = min(self._radius, h / 2)
        paint_round(self, 0, 0, w, h, r, T.FIELD, self._surface)

        n = max(1, len(self._opts))
        inner = w - 6
        iw = inner / n
        x = 3 + self._pos * iw
        paint_round(self, x, 3, x + iw, h - 3, max(4, r - 4), T.ACCENT, T.FIELD)

        for i, (label, _) in enumerate(self._opts):
            cx = 3 + (i + 0.5) * iw
            fg = '#ffffff' if abs(self._pos - i) < 0.5 else T.MUTED
            self.create_text(cx, h / 2, text=label, fill=fg, font=self._font)

    def _ease_override(self):
        pass

    def _on_click(self, event):
        w = max(self._cw, 8)
        iw = (w - 6) / max(1, len(self._opts))
        idx = int((event.x - 3) // iw)
        idx = max(0, min(len(self._opts) - 1, idx))
        idx = max(0, min(len(self._opts) - 1, idx))
        self.variable.set(self._opts[idx][1])
        self.ease_to(float(idx))
        if self._command:
            self._command()

    # 复用基类缓动：把进度映射成索引位置
    def ease_to(self, target):
        self._ease_target = float(target)
        if self._job is None:
            self._job = self.after(_TICK, self._index_tick)

    def _index_tick(self):
        self._job = None
        d = self._ease_target - self._ease
        if abs(d) < 0.012:
            self._ease = self._ease_target
            self._pos = self._ease
            self.render()
            return
        self._ease += d * 0.30
        self._pos = self._ease
        self.render()
        self._job = self.after(_TICK, self._index_tick)

    def set(self, value):
        self.ease_to(self._index_of(value))


#圆角输入框
class RoundedEntry(_Base):
    def __init__(self, master, textvariable=None, width=104, height=32, radius=10,
                 surface=T.CARD, justify='right', font=None):
        super().__init__(master, surface, width=width, height=height)
        self._radius = radius
        self._font = font or (FONT, 9)
        self._focus = 0.0
        self.enabled = True
        self.entry = tk.Entry(self, textvariable=textvariable, bd=0, relief='flat',
                              bg=T.FIELD, fg=T.TEXT, insertbackground=T.ACCENT,
                              highlightthickness=0, justify=justify, font=self._font,
                              disabledbackground=T.FIELD, disabledforeground=T.MUTED,
                              selectbackground=T.ACCENT, selectforeground='#ffffff')
        self._win = self.create_window(11, height / 2, anchor='w', window=self.entry,
                                       width=width - 22, height=height - 10)
        self.entry.bind('<FocusIn>', lambda e: self.ease_to(1))
        self.entry.bind('<FocusOut>', lambda e: self.ease_to(0))
        self.bind('<Button-1>', lambda e: self.entry.focus_set())
        self.after(0, self.render)

    def render(self):
        self.delete('tag_line')
        self._img_refs = self._img_refs[-4:]
        w, h = max(self._cw, 8), max(self._ch, 8)
        field = T.FIELD if self.enabled else T.DISABLED
        line = mix(T.LINE, T.ACCENT, self._focus) if self.enabled else T.LINE
        paint_round(self, 0, 0, w, h, self._radius, field, self._surface,
                    outline=line, ow=1, tags='tag_line')
        self.itemconfigure(self._win, width=max(10, w - 22), height=max(10, h - 10))
        self.coords(self._win, 11, h / 2)
        try:
            self.entry.configure(bg=field, disabledbackground=field)
        except tk.TclError:
            pass

    def configure(self, cnf=None, **kw):
        state = kw.pop('state', None)
        if state is not None:
            self.enabled = (state == 'normal')
            try:
                self.entry.configure(state=state)
            except tk.TclError:
                pass
        if cnf or kw:
            try:
                tk.Canvas.configure(self, cnf or {}, **kw)
            except tk.TclError:
                pass
        self.render()

    config = configure


# 圆角外壳&下拉框
class ComboField(_Base):
    """
    """

    def __init__(self, master, textvariable, values=(), surface=T.CARD,
                 height=32, radius=10, width=200, command=None):
        super().__init__(master, surface, width=width, height=height)
        self._radius = radius
        self._command = command
        self.combo = ttk.Combobox(self, textvariable=textvariable, values=list(values),
                                  state='readonly', style='Dark.TCombobox',
                                  font=(FONT, 9))
        self._win = self.create_window(0, 0, anchor='nw', window=self.combo)
        self.combo.bind('<<ComboboxSelected>>', self._on_selected)
        self.combo.bind('<FocusIn>', lambda e: self.ease_to(1))
        self.combo.bind('<FocusOut>', lambda e: self.ease_to(0))
        self.combo.bind('<Enter>', lambda e: self.ease_to(1))
        self.combo.bind('<Leave>', self._on_leave)
        self.after(20, self._layout)

    def _on_selected(self, _=None):
        self.ease_to(0)
        if self._command:
            self._command()

    def _on_leave(self, _=None):
        try:
            focused = self.focus_get()
        except KeyError:
            focused = None
        if focused is not self.combo:
            self.ease_to(0)

    def _on_configure(self, event):
        if event.width != self._cw or event.height != self._ch:
            self._cw, self._ch = event.width, event.height
            self._layout()

    def _layout(self):
        w, h = max(self._cw, 60), max(self._ch, 20)
        self.coords(self._win, 10, 4)
        self.itemconfigure(self._win, width=max(24, w - 20), height=max(12, h - 8))
        self.render()

    def render(self):
        self.delete('bg')
        self._img_refs = self._img_refs[-1:]
        w, h = max(self._cw, 8), max(self._ch, 8)
        line = mix(T.LINE, T.ACCENT, self._ease)
        paint_round(self, 0, 0, w, h, self._radius, T.FIELD, self._surface,
                    outline=line, ow=1, tags='bg')


#进度条
class Progress(_Base):
    def __init__(self, master, height=6, radius=3, surface=T.BG, fill=T.ACCENT):
        super().__init__(master, surface, width=200, height=height)
        self._radius = radius
        self._fill = fill
        self._cur = 0.0
        self._target = 0.0
        self._job = None
        self._img_refs = []
        self.after(0, self.render)

    def set(self, frac, color=None):
        self._target = max(0.0, min(1.0, float(frac)))
        if color:
            self._fill = color
        if self._job is None:
            self._job = self.after(_TICK, self._tick)

    def _tick(self):
        self._job = None
        d = self._target - self._cur
        if abs(d) < 0.004:
            self._cur = self._target
            self.render()
            return
        self._cur += d * 0.25
        self.render()
        self._job = self.after(_TICK, self._tick)

    def render(self):
        self.delete('all')
        self._img_refs.clear()
        w, h = max(self._cw, 8), max(self._ch, 8)
        r = min(self._radius, h / 2)
        paint_round(self, 0, 0, w, h, r, T.FIELD, self._surface)
        if self._cur > 0.002:
            fw = max(h, w * self._cur)
            paint_round(self, 0, 0, fw, h, r, self._fill, T.FIELD)


#卡片容器
class Card(tk.Canvas):
    """尺寸自适应内容的圆角卡片，子控件塞进 card.body"""

    def __init__(self, master, pad=12, radius=16, surface=T.BG, fill=T.CARD,
                 stroke=T.LINE):
        super().__init__(master, bg=surface, highlightthickness=0, bd=0,
                         width=372, height=44, takefocus=0)
        self.pad, self.radius = pad, radius
        self.surface, self.fill, self.stroke = surface, fill, stroke
        self._img_refs = []
        self._last = (0, 0)
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(pad, pad, anchor='nw', window=self.body)
        self.bind('<Configure>', self._sync)
        self.body.bind('<Configure>', self._sync)
        self.after(12, self._sync)

    def _sync(self, _=None):
        w = max(self.winfo_width(), 10)
        bh = self.body.winfo_reqheight()
        need = bh + self.pad * 2
        if abs(self.winfo_height() - need) > 1:
            self.configure(height=need)
        self.itemconfigure(self._win, width=max(10, w - self.pad * 2), height=bh)
        self.coords(self._win, self.pad, self.pad)
        if (w, need) != self._last:
            self._last = (w, need)
            self._render(w, need)

    def _render(self, w, h):
        self.delete('cardbg')
        self._img_refs = self._img_refs[-2:]
        if h < 4 or w < 4:
            return
        paint_round(self, 1, 1, w - 1, h - 1, self.radius, self.fill, self.surface,
                    outline=self.stroke, ow=1, tags='cardbg')
#  主程序
class ClickerApp:
    def __init__(self, root):
        self.root = root
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.drag_offset = None
        self.pick_offset = None
        self.pick_hwnd = None
        self.pick_active = False
        self.emergency = False
        self.running = False

        self._status_job = None
        self._pulse_job = None
        # 子线程不能直接碰控件（tkinter 只允许主线程调用），统一走这个队列
        self.ui_queue = queue.Queue()

        self.win_var = tk.StringVar()
        self.sel_hwnd = None          # 选中的目标窗口句柄（身份，不随标题变化）
        self.click_method = tk.StringVar(value='physical')
        self.click_type = tk.StringVar(value='single')
        self.mouse_button = tk.StringVar(value='left')
        self.pos_mode = tk.StringVar(value='random')
        self.n_var = tk.StringVar(value='100')
        self.dur_var = tk.StringVar(value='0.5')
        self.int_var = tk.StringVar(value='0.2')
        self._window_list = []

        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.configure(bg=T.BG)

        self._setup_style()
        self._build_ui()
        self._refresh_windows()

        # 全局热键监听
        threading.Thread(target=self._hotkey_listener, daemon=True).start()

        # 先撑开一个足够大的画布让卡片算出真实高度，随后再收紧窗口
        root.geometry(f'{self.WIDTH}x760+110+70')
        root.attributes('-alpha', 0.0)
        root.after(40, self._fit_window)
        root.after(60, self._pump_queue)
        root.after(1600, self._watch_target)

    WIDTH = 400

    def _fit_window(self, passes=4):
        """等布局收敛后按内容定高，并裁出圆角窗口 + 淡入"""
        try:
            self.root.update_idletasks()
        except tk.TclError:
            return
        h = max(520, min(self.root.winfo_reqheight(),
                         self.root.winfo_screenheight() - 80))
        self.root.geometry(f'{self.WIDTH}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}')
        self.root.update_idletasks()
        if passes > 0:
            self.root.after(35, lambda: self._fit_window(passes - 1))
        else:
            h = max(520, self.root.winfo_reqheight())
            self.root.geometry(
                f'{self.WIDTH}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}')
            self.root.update_idletasks()
            round_window(self.root, self.WIDTH, h, 18)
            self._fade_in(0.0)

    #线程&界面
    def _post(self, func, *args):
        """子线程里安全地把调用排给主线程"""
        self.ui_queue.put((func, args))

    def _pump_queue(self):
        """主线程里定时取出子线程的请求并执行"""
        try:
            while True:
                func, args = self.ui_queue.get_nowait()
                try:
                    func(*args)
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            self.root.after(40, self._pump_queue)
        except tk.TclError:
            pass

    #动效
    def _fade_in(self, t):
        t = min(1.0, t + 0.09)
        alpha = 0.96 * (1 - (1 - t) ** 3)
        try:
            self.root.attributes('-alpha', alpha)
        except tk.TclError:
            return
        if t < 1.0:
            self.root.after(_TICK, lambda: self._fade_in(t))

    def _pulse(self):
        self._pulse_job = None
        if not (self.running and self.root.winfo_exists()):
            self.dot.itemconfigure(self._dot, fill=T.MUTED)
            return
        k = 0.5 + 0.5 * math.sin(time.time() * 5.5)
        self.dot.itemconfigure(self._dot, fill=mix(T.GREEN, '#b6f2da', k))
        self._pulse_job = self.root.after(40, self._pulse)

    def _start_pulse(self):
        if self._pulse_job is None:
            self._pulse()

    def _stop_pulse(self):
        if self._pulse_job:
            self.root.after_cancel(self._pulse_job)
            self._pulse_job = None
        self.dot.itemconfigure(self._dot, fill=T.MUTED)

    def _set_status(self, text, color=T.MUTED, hold=2.4):
        self._status_from = color
        self.status_lbl.configure(text=text, fg=color)
        if self._status_job:
            self.root.after_cancel(self._status_job)
            self._status_job = None
        if color != T.MUTED:
            self._status_job = self.root.after(int(hold * 1000), self._status_fade)

    def _status_fade(self, t=0.0):
        t = min(1.0, t + 0.07)
        self.status_lbl.configure(fg=mix(self._status_from, T.MUTED, t))
        if t < 1.0:
            self._status_job = self.root.after(_TICK, lambda: self._status_fade(t))
        else:
            self._status_job = None

    # ---------------- 主题样式 ----------------
    def _setup_style(self):
        """把原生 Combobox 调成和深色卡片一致的样式"""
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Dark.TCombobox',
                        fieldbackground=T.FIELD, background=T.FIELD,
                        foreground=T.TEXT, arrowcolor=T.MUTED,
                        bordercolor=T.FIELD, lightcolor=T.FIELD, darkcolor=T.FIELD,
                        insertcolor=T.TEXT, padding=(2, 3), relief='flat',
                        borderwidth=0, arrowsize=13, font=(FONT, 9))
        style.map('Dark.TCombobox',
                  fieldbackground=[('readonly', T.FIELD), ('disabled', T.DISABLED)],
                  background=[('readonly', T.FIELD), ('active', T.FIELD_HI),
                              ('disabled', T.DISABLED)],
                  foreground=[('readonly', T.TEXT), ('disabled', T.MUTED)],
                  arrowcolor=[('active', T.ACCENT), ('disabled', T.MUTED)],
                  bordercolor=[('focus', T.FIELD), ('active', T.FIELD)],
                  lightcolor=[('focus', T.FIELD), ('active', T.FIELD)],
                  darkcolor=[('focus', T.FIELD), ('active', T.FIELD)])
        # 系统弹层（下拉列表）也调深
        for opt, val in (('*TCombobox*Listbox.background', T.CARD),
                         ('*TCombobox*Listbox.foreground', T.TEXT),
                         ('*TCombobox*Listbox.selectBackground', T.ACCENT),
                         ('*TCombobox*Listbox.selectForeground', '#ffffff'),
                         ('*TCombobox*Listbox.font', '{Microsoft YaHei UI} 9'),
                         ('*TCombobox*Listbox.borderWidth', '0'),
                         ('*TCombobox*Listbox.highlightThickness', '0'),
                         ('*TCombobox*Listbox.relief', 'flat'),
                         ('*TCombobox*Listbox.activeStyle', 'none')):
            self.root.option_add(opt, val)
        # 弹层里的滚动条
        style.configure('Vertical.TScrollbar', background=T.FIELD_HI,
                        troughcolor=T.CARD, bordercolor=T.CARD, arrowcolor=T.MUTED,
                        lightcolor=T.FIELD_HI, darkcolor=T.FIELD_HI,
                        relief='flat', arrowsize=12, borderwidth=0)
        style.map('Vertical.TScrollbar',
                  background=[('active', T.ACCENT), ('pressed', T.ACCENT)])

    #界面构建
    def _build_ui(self):
        root = self.root

        #顶栏
        header = tk.Frame(root, bg=T.BG, height=42)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)

        mark = tk.Canvas(header, width=16, height=16, bg=T.BG, highlightthickness=0, bd=0)
        mark.pack(side='left', padx=(16, 8))
        mark.create_oval(2, 2, 14, 14, fill=T.ACCENT, outline='')

        tk.Label(header, text='悬浮点击器', bg=T.BG, fg=T.TEXT,
                 font=(FONT, 10, 'bold')).pack(side='left')

        RoundedButton(header, text='✕', command=root.destroy, kind='ghost', width=28,
                      height=24, radius=8, surface=T.BG, font=(FONT, 9)
                      ).pack(side='right', padx=(0, 12))
        RoundedButton(header, text='—', command=self._minimize, kind='ghost', width=28,
                      height=24, radius=8, surface=T.BG, font=(FONT, 9)
                      ).pack(side='right', padx=(0, 6))

        content = tk.Frame(root, bg=T.BG)
        content.pack(fill='both', expand=True, padx=14)

        #卡片一：目标窗口
        c1 = Card(content)
        c1.pack(fill='x')
        b = c1.body
        self._tag(b, '目标窗口')
        row = tk.Frame(b, bg=T.CARD)
        row.pack(fill='x', pady=(7, 0))
        self.win_field = ComboField(row, self.win_var, surface=T.CARD, height=32,
                                    command=self._on_window_picked)
        self.win_field.pack(side='left', fill='x', expand=True)
        self.win_combo = self.win_field.combo
        RoundedButton(row, text='刷新', command=self._refresh_windows, kind='soft',
                      width=58, height=32, radius=10, surface=T.CARD,
                      font=(FONT, 9)).pack(side='left', padx=(8, 0))

        self.target_hint = tk.Label(b, text='未选择目标窗口', bg=T.CARD, fg=T.MUTED,
                                    font=(FONT, 8), anchor='w')
        self.target_hint.pack(fill='x', pady=(7, 0))

        #卡片二：点击参数
        c2 = Card(content)
        c2.pack(fill='x', pady=(10, 0))
        b = c2.body
        self._tag(b, '点击参数')

        self._tag(b, '注入方式', gap=11)
        self.seg_method = Segmented(b, [('物理点击', 'physical'), ('后台注入 · 不占鼠标', 'inject')],
                                    self.click_method, surface=T.CARD)
        self.seg_method.pack(fill='x', pady=(6, 0))

        self._tag(b, '点击方式', gap=11)
        self.seg_type = Segmented(b, [('单击', 'single'), ('长按', 'hold')], self.click_type,
                                  command=self._toggle_hold, surface=T.CARD)
        self.seg_type.pack(fill='x', pady=(6, 0))

        self._tag(b, '鼠标按键', gap=11)
        self.seg_mouse = Segmented(b, [('左键', 'left'), ('右键', 'right'), ('中键', 'middle')],
                                   self.mouse_button, surface=T.CARD)
        self.seg_mouse.pack(fill='x', pady=(6, 0))

        self._tag(b, '数值', gap=11)
        grid = tk.Frame(b, bg=T.CARD)
        grid.pack(fill='x', pady=(8, 0))
        fields = [('点击次数', self.n_var), ('按住时长 · 秒', self.dur_var),
                  ('点击间隔 · 秒', self.int_var)]
        self._entries = []
        for i, (label, var) in enumerate(fields):
            col = tk.Frame(grid, bg=T.CARD)
            col.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 9, 0))
            grid.grid_columnconfigure(i, weight=1, uniform='param')
            tk.Label(col, text=label, bg=T.CARD, fg=T.MUTED, font=(FONT, 8)
                     ).pack(anchor='w')
            ent = RoundedEntry(col, textvariable=var, height=30, surface=T.CARD,
                               justify='center')
            ent.pack(fill='x', pady=(5, 0))
            self._entries.append(ent)
        self.dur_entry = self._entries[1]
        self._toggle_hold()

        #卡片三：点击位置
        c3 = Card(content)
        c3.pack(fill='x', pady=(10, 0))
        b = c3.body
        self._tag(b, '点击位置')
        self.seg_pos = Segmented(b, [('窗口内随机', 'random'), ('窗口中心', 'center'),
                                     ('拾取坐标', 'pick')], self.pos_mode,
                                 command=self._toggle_pick_ui, surface=T.CARD)
        self.seg_pos.pack(fill='x', pady=(7, 0))

        prow = tk.Frame(b, bg=T.CARD)
        prow.pack(fill='x', pady=(12, 0))
        self.btn_pick = RoundedButton(prow, text='拾取位置', command=self._start_pick,
                                      kind='primary', width=96, height=32, radius=10,
                                      surface=T.CARD, font=(FONT, 9, 'bold'))
        self.btn_pick.pack(side='left')
        self.pick_status = tk.Label(prow, text='未拾取', bg=T.CARD, fg=T.MUTED,
                                    font=(FONT, 9), anchor='w')
        self.pick_status.pack(side='left', padx=10)

        #底部：进度 / 状态 / 控制
        footer = tk.Frame(root, bg=T.BG)
        footer.pack(fill='x', padx=14, pady=(14, 16))
        self.footer = footer

        self.progress = Progress(footer, surface=T.BG)
        self.progress.pack(fill='x')

        srow = tk.Frame(footer, bg=T.BG)
        srow.pack(fill='x', pady=(9, 10))
        self.dot = tk.Canvas(srow, width=14, height=14, bg=T.BG, highlightthickness=0, bd=0)
        self.dot.pack(side='left')
        self._dot = self.dot.create_oval(4, 4, 11, 11, fill=T.MUTED, outline='')
        self.status_lbl = tk.Label(srow, text='就绪', bg=T.BG, fg=T.MUTED,
                                   font=(FONT, 9), anchor='w')
        self.status_lbl.pack(side='left', padx=(6, 0))

        btns = tk.Frame(footer, bg=T.BG)
        btns.pack(fill='x')
        self.btn_start = RoundedButton(btns, text='开始', command=self._start, kind='success',
                                       height=40, radius=12, surface=T.BG,
                                       font=(FONT, 10, 'bold'))
        self.btn_start.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.btn_stop = RoundedButton(btns, text='停止', command=self._stop, kind='danger',
                                      height=40, radius=12, surface=T.BG,
                                      font=(FONT, 10, 'bold'), enabled=False)
        self.btn_stop.pack(side='left', fill='x', expand=True, padx=(5, 0))

        tk.Label(footer, text=f'{START_HOTKEY} 开始　·　{STOP_HOTKEY} 紧急终止',
                 bg=T.BG, fg='#5a5a70', font=(FONT, 8)).pack(pady=(10, 0))

        self._toggle_pick_ui()
        self._bind_drag(root)

    def _tag(self, parent, text, gap=0):
        tk.Label(parent, text=text, bg=T.CARD, fg=T.MUTED, font=(FONT, 8)
                 ).pack(anchor='w', pady=(gap, 0))

    #交互逻辑
    def _minimize(self):
        try:
            self.root.iconify()
        except tk.TclError:
            pass

    def _toggle_hold(self):
        if hasattr(self, 'dur_entry'):
            self.dur_entry.configure(
                state='normal' if self.click_type.get() == 'hold' else 'disabled')

    def _toggle_pick_ui(self):
        on = self.pos_mode.get() == 'pick'
        self.btn_pick.configure(state='normal' if on else 'disabled')
        self.pick_status.configure(fg=T.MUTED if on else '#4d4d60')

    def _refresh_windows(self):
        """重扫窗口：下拉框只负责显示标题，真正记住的是句柄"""
        self._window_list = enum_visible_windows()
        titles = [t for _, t in self._window_list]
        hwnds = [h for h, _ in self._window_list]
        self.win_combo['values'] = titles

        if self.sel_hwnd in hwnds:
            idx = hwnds.index(self.sel_hwnd)      # 标题变了也认得出来
        elif titles:
            idx = 0
        else:
            idx = -1

        if idx >= 0:
            self.sel_hwnd = hwnds[idx]
            self.win_combo.current(idx)
            self.win_var.set(titles[idx])
        else:
            self.sel_hwnd = None
            self.win_var.set('')
        self._update_target_hint()
        self._set_status(f'已发现 {len(titles)} 个窗口')

    def _on_window_picked(self, _=None):
        """用户在下拉列表里选了一项：按索引取句柄，不去比对标题"""
        idx = self.win_combo.current()
        if 0 <= idx < len(self._window_list):
            self.sel_hwnd = self._window_list[idx][0]
        self._update_target_hint()

    def _get_selected_hwnd(self):
        """当前选中的窗口句柄"""
        return self.sel_hwnd

    def _title_of(self, hwnd):
        """实时标题，仅用于界面显示"""
        if hwnd:
            title = get_window_title(hwnd)
            if title:
                return title
        for h, t in self._window_list:
            if h == hwnd:
                return t
        return ''

    @staticmethod
    def _short(text, n=18):
        return text if len(text) <= n else text[:n] + '…'

    def _update_target_hint(self):
        hwnd = self.sel_hwnd
        if not hwnd:
            self.target_hint.configure(text='未选择目标窗口', fg=T.MUTED)
        elif not is_window_valid(hwnd):
            self.target_hint.configure(text='目标窗口已关闭，请点刷新重新选择', fg=T.RED)
        else:
            self.target_hint.configure(
                text='已锁定：' + self._short(self._title_of(hwnd)), fg=T.MUTED)

    def _watch_target(self):
        """常驻轻量巡检：目标被关掉立刻提示；标题变了只更新显示，不动句柄"""
        self._update_target_hint()
        if self.sel_hwnd and is_window_valid(self.sel_hwnd):
            title = get_window_title(self.sel_hwnd)
            idx = self.win_combo.current()
            values = list(self.win_combo['values'])
            if title and 0 <= idx < len(values) and values[idx] != title:
                values[idx] = title
                self.win_combo['values'] = values
                self.win_combo.current(idx)
                self.win_var.set(title)
        self.root.after(1500, self._watch_target)

    def _require_target(self):
        """取有效目标；失效则自动重扫一次，要是还无效才报错"""
        hwnd = self._get_selected_hwnd()
        if hwnd and is_window_valid(hwnd):
            return hwnd
        self._refresh_windows()
        hwnd = self._get_selected_hwnd()
        if hwnd and is_window_valid(hwnd):
            self._set_status('目标窗口已重新匹配', T.GREEN)
            return hwnd
        messagebox.showerror('目标窗口无效',
                             '选中的窗口已经被关闭了。\n请点「刷新」重新选择一个窗口。')
        return None

    def _bind_drag(self, root):
        interactive = (RoundedButton, Segmented, ComboField, RoundedEntry,
                       ttk.Combobox, tk.Entry, tk.Listbox, tk.Button, tk.Scale)

        def on_press(event):
            if isinstance(event.widget, interactive):
                return
            self.drag_offset = (event.x_root - root.winfo_x(),
                                event.y_root - root.winfo_y())

        def on_move(event):
            if self.drag_offset:
                x = event.x_root - self.drag_offset[0]
                y = event.y_root - self.drag_offset[1]
                root.geometry(f'+{x}+{y}')

        def on_release(_):
            self.drag_offset = None

        root.bind('<ButtonPress-1>', on_press, add='+')
        root.bind('<B1-Motion>', on_move, add='+')
        root.bind('<ButtonRelease-1>', on_release, add='+')

    def _validate_inputs(self):
        try:
            n = int(self.n_var.get())
            dur = float(self.dur_var.get())
            interval = float(self.int_var.get())
            if n <= 0:
                raise ValueError('次数必须为正整数')
            if dur < 0 or interval < 0:
                raise ValueError('时长/间隔不能为负')
        except ValueError as e:
            messagebox.showerror('参数错误', str(e))
            return None
        return n, dur, interval

    #物理鼠标拾取位置
    def _start_pick(self):
        if self.running:
            return
        hwnd = self._require_target()
        if hwnd is None:
            return

        self.root.withdraw()
        tip = tk.Toplevel(self.root)
        tip.overrideredirect(True)
        tip.attributes('-topmost', True)
        tip.attributes('-alpha', 0.0)
        tip.configure(bg=T.CARD)
        tk.Label(tip, text=f'请在目标窗口内点击左键选取位置（{PICK_TIMEOUT} 秒）',
                 bg=T.CARD, fg=T.TEXT, font=(FONT, 10, 'bold'),
                 justify='center').pack(padx=22, pady=(14, 4))
        tk.Label(tip, text=self._title_of(hwnd) or '（窗口）', bg=T.CARD, fg=T.ACCENT,
                 font=(FONT, 9), justify='center').pack(padx=22, pady=(0, 14))
        tip.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = tip.winfo_reqwidth(), tip.winfo_reqheight()
        tip.geometry(f'{w}x{h}+{(sw - w) // 2}+{sh - h - 60}')
        tip.update_idletasks()
        round_window(tip, w, h, 14)
        tip.attributes('-alpha', 0.97)

        self.pick_status.configure(text='正在拾取…', fg=T.ACCENT)
        self.pick_active = True
        threading.Thread(target=self._listen_pick, args=(tip, hwnd), daemon=True).start()

    def _listen_pick(self, tip, hwnd):
        start = time.time()
        prev_down = False
        picked = None
        while time.time() - start < PICK_TIMEOUT:
            down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
            if down and not prev_down:
                x, y = get_cursor_pos()
                if is_window_valid(hwnd):
                    left, top, right, bottom = get_window_rect(hwnd)
                    if left <= x <= right and top <= y <= bottom:
                        picked = (x, y, left, top)
                        break
            prev_down = down
            time.sleep(0.02)

        self._post(self._finish_pick, tip, picked)

    def _finish_pick(self, tip, picked):
        try:
            tip.destroy()
        except Exception:
            pass
        self.root.deiconify()
        self.pick_active = False

        if picked:
            x, y, left, top = picked
            self.pick_offset = (x - left, y - top)
            self.pick_hwnd = self._get_selected_hwnd()
            self.pick_status.configure(text=f'已拾取 ({x}, {y})', fg=T.GREEN)
            self._set_status(f'拾取位置：({x}, {y})', T.GREEN)
        else:
            self.pick_offset = None
            self.pick_hwnd = None
            self.pick_status.configure(text='拾取超时，请重试', fg=T.RED)
            self._set_status('拾取超时，请重试', T.RED)

    #全局快捷键
    def _hotkey_listener(self):
        """全局监听 Ctrl+Alt+PageUp(开始) / Ctrl+Alt+PageDown(紧急终止)，轮询方式"""
        while True:
            try:
                ctrl = (user32.GetAsyncKeyState(VK_LCONTROL) & 0x8000 or
                        user32.GetAsyncKeyState(VK_RCONTROL) & 0x8000)
                alt = (user32.GetAsyncKeyState(VK_LMENU) & 0x8000 or
                       user32.GetAsyncKeyState(VK_RMENU) & 0x8000)
                pgup = user32.GetAsyncKeyState(VK_PRIOR) & 0x8000
                pgdn = user32.GetAsyncKeyState(VK_NEXT) & 0x8000
                if ctrl and alt and pgup:
                    self._post(self._hotkey_start)
                    time.sleep(0.5)      # 防抖，避免连续触发
                elif ctrl and alt and pgdn:
                    self._post(self._emergency_stop)
                    time.sleep(0.5)
            except Exception:
                pass
            time.sleep(0.05)

    def _hotkey_start(self):
        if self.pick_active:
            self._set_status('拾取进行中，忽略开始键', T.RED)
            return
        if self.running or self.worker_thread and self.worker_thread.is_alive():
            return
        self._start()

    def _emergency_stop(self):
        self.emergency = True
        self.stop_event.set()
        self._set_status(f'紧急终止（{STOP_HOTKEY}）', T.RED)
        if not (self.worker_thread and self.worker_thread.is_alive()):
            self._reset_buttons()

    def _reset_buttons(self):
        self.btn_start.configure(state='normal')
        self.btn_stop.configure(state='disabled')

    #点击执行
    def _start(self):
        if self.running or (self.worker_thread and self.worker_thread.is_alive()):
            return
        params = self._validate_inputs()
        if not params:
            return
        n, dur, interval = params

        hwnd = self._require_target()
        if hwnd is None:
            return

        mode = self.pos_mode.get()
        if mode == 'pick' and not self.pick_offset:
            messagebox.showerror('错误', '请先拾取点击位置')
            return

        self.emergency = False
        self.stop_event.clear()
        self.running = True
        self.btn_start.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.progress.set(0.0, T.ACCENT)
        method_label = '物理点击' if self.click_method.get() == 'physical' else '后台注入'
        self._set_status(f'{method_label} → {self._short(self._title_of(hwnd), 14)}',
                         T.ACCENT, hold=99)
        self._start_pulse()

        args = (hwnd, n, dur, interval, mode, self.click_type.get() == 'hold',
                self.mouse_button.get(), self.click_method.get(), self.win_var.get())
        self.worker_thread = threading.Thread(target=self._work, args=args, daemon=True)
        self.worker_thread.start()

    def _work(self, hwnd, n, dur, interval, mode, is_hold, button, method, title):
        done = 0
        for i in range(n):
            if self.stop_event.is_set():
                break
            if not is_window_valid(hwnd):
                self._post(self._set_status, '目标窗口已关闭，自动停止', T.RED)
                break

            left, top, right, bottom = get_window_rect(hwnd)
            if right - left < 4 or bottom - top < 4:
                self._post(self._set_status, '窗口尺寸异常，跳过', T.RED)
                time.sleep(interval)
                continue

            if mode == 'center':
                x, y = (left + right) // 2, (top + bottom) // 2
            elif mode == 'pick':
                if self.pick_offset and self.pick_hwnd == hwnd:
                    dx, dy = self.pick_offset
                    x, y = left + dx, top + dy
                else:
                    self._post(self._set_status, '拾取目标失效，停止', T.RED)
                    break
            else:  # random —— 仅在窗口范围内随机
                x = random.randint(left + 2, right - 2)
                y = random.randint(top + 2, bottom - 2)

            if method == 'inject':
                inject_click(hwnd, x, y, button, dur, is_hold, interval, self.stop_event)
            else:
                click_at(x, y, button, dur, is_hold, interval, self.stop_event)
            done += 1
            if done % 3 == 0 or done == n:
                self._post(self._on_progress, done, n)

        self._post(self._finish, done, n)

    def _on_progress(self, done, total):
        if self.running:
            self.progress.set(done / total)
            self.status_lbl.configure(text=f'已点击 {done} / {total}')

    def _finish(self, done, total):
        self.running = False
        self._reset_buttons()
        self._stop_pulse()
        if self.emergency:
            self.progress.set(done / total, T.RED)
            self._set_status(f'已紧急终止（{STOP_HOTKEY}）　完成 {done}/{total}', T.RED)
            self.emergency = False
        elif self.stop_event.is_set():
            self.progress.set(done / total, T.RED)
            self._set_status(f'已停止　完成 {done}/{total}', T.RED)
        else:
            self.progress.set(1.0, T.GREEN)
            self._set_status(f'完成 {done}/{total}', T.GREEN)

    def _stop(self):
        self.stop_event.set()
        self.status_lbl.configure(text='正在停止……')


def main():
    root = tk.Tk()
    ClickerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
    