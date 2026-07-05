# -*- coding: utf-8 -*-
"""生成技术方案设计图（7张PNG）。彩色专业风格，PingFang SC 字体。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
from matplotlib.lines import Line2D
from pathlib import Path

OUT = Path(__file__).parent / "diagrams"
OUT.mkdir(exist_ok=True)

# 配色
C_PRIMARY = "#1F497D"
C_SECOND = "#2E5C8A"
C_BLUE_FILL = "#D6E4F0"
C_GREEN = "#4F8A4F"
C_GREEN_FILL = "#D9EBD9"
C_ORANGE = "#D97706"
C_ORANGE_FILL = "#FCE7CF"
C_RED = "#C0392B"
C_RED_FILL = "#F8D7D5"
C_GRAY = "#555555"
C_GRAY_FILL = "#EEF1F5"
C_PURPLE = "#6B5B95"
C_PURPLE_FILL = "#E5E0EF"

plt.rcParams["font.family"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def _box(ax, x, y, w, h, text, fc=C_BLUE_FILL, ec=C_PRIMARY, fs=9, tc="#222", lw=1.4, rounded=True):
    style = "round,pad=0.02,rounding_size=0.08" if rounded else "square,pad=0.02"
    p = FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=lw)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs, color=tc, wrap=True)


def _diamond(ax, x, y, w, h, text, fc=C_ORANGE_FILL, ec=C_ORANGE, fs=8.5):
    from matplotlib.patches import Polygon
    pts = [(x, y+h/2), (x+w/2, y+h), (x+w, y+h/2), (x+w/2, y)]
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=ec, lw=1.4))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs)


def _arrow(ax, x1, y1, x2, y2, text="", color=C_GRAY, ls="-", fs=7.5, offset=0):
    ar = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                         color=color, lw=1.3, linestyle=ls,
                         connectionstyle="arc3,rad=0")
    ax.add_patch(ar)
    if text:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my + 0.12 + offset, text, ha="center", va="center", fontsize=fs,
                color=color, bbox=dict(fc="white", ec="none", pad=1))


def _layer(ax, x, y, w, h, title, color_fill, color_edge, modules, fs_title=10):
    ax.add_patch(Rectangle((x, y), w, h, fc=color_fill, ec=color_edge, lw=1.6, alpha=0.35))
    ax.text(x + 0.15, y + h - 0.25, title, fontsize=fs_title, fontweight="bold", color=color_edge)
    # modules
    n = len(modules)
    mw = (w - 0.4 - 0.2*(n-1)) / n
    mx = x + 0.2
    for m in modules:
        _box(ax, mx, y + 0.25, mw, h - 0.6, m, fc="white", ec=color_edge, fs=8.5)
        mx += mw + 0.2


def fig_setup(w=12, h=7):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


# ============ 图1：总体技术架构图 ============
def diagram1_architecture():
    fig, ax = fig_setup(12, 8.5)
    ax.set_title("图1  数据采集通道总体技术架构", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    # 四层从上到下
    _layer(ax, 0.5, 6.7, 11, 1.3, "调度编排层", C_BLUE_FILL, C_PRIMARY,
           ["任务扫描器", "CrawlerManager\n(单例·Lock串行)", "subprocess\n调度器", "状态/日志管理"], fs_title=10)
    _layer(ax, 0.5, 4.9, 11, 1.3, "采集引擎层", C_GREEN_FILL, C_GREEN,
           ["CDPBrowserManager\n(Chrome实例)", "平台Crawler\n(xhs/dy/weibo...)", "登录态管理\n(profile缓存)", "反爬策略\n(代理/频率/签名)"], fs_title=10)
    _layer(ax, 0.5, 3.1, 11, 1.3, "数据适配层", C_ORANGE_FILL, C_ORANGE,
           ["字段映射适配器\n(每平台一份)", "类型转换器\n(时间/计数)", "local_db_item\n构造器", "ContextVar\n(source_keyword)"], fs_title=10)
    _layer(ax, 0.5, 1.3, 11, 1.3, "标准化输出层", C_PURPLE_FILL, C_PURPLE,
           ["StoreFactory\n(8后端分发)", "去重检查\n(content_is_exist)", "upsert\n(update/add)", "统一数据池\nsource_items"], fs_title=10)

    # 数据流向箭头
    _arrow(ax, 6, 6.7, 6, 6.25, "派发任务", C_PRIMARY, fs=8)
    _arrow(ax, 6, 4.9, 6, 4.45, "原始数据\nnote_item:Dict", C_GREEN, fs=8)
    _arrow(ax, 6, 3.1, 6, 2.65, "归一化\nlocal_db_item:Dict", C_ORANGE, fs=8)
    _arrow(ax, 6, 1.3, 6, 0.95, "标准化数据", C_PURPLE, fs=8)
    _box(ax, 4.4, 0.3, 3.2, 0.6, "平台数据池 (analysis_status=pending)", fc=C_RED_FILL, ec=C_RED, fs=9)

    # 左侧数据契约标注
    ax.annotate("", xy=(0.35, 6.7), xytext=(0.35, 1.3),
                arrowprops=dict(arrowstyle="<->", color=C_GRAY, lw=0.8, ls=":"))
    ax.text(0.15, 4, "跨层\n数据契约\n(单向流转)", ha="center", va="center", fontsize=8, color=C_GRAY, rotation=90)

    fig.savefig(OUT/"fig1_architecture.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============ 图2：采集执行时序图 ============
def diagram2_sequence():
    fig, ax = fig_setup(13, 8.5)
    ax.set_title("图2  单次采集任务执行时序", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    actors = ["调度器", "CrawlerManager", "main.py\n(子进程)", "平台API", "StoreFactory"]
    xs = [1.5, 4.0, 6.5, 9.0, 11.5]
    for a, x in zip(actors, xs):
        _box(ax, x-1.0, 7.6, 2.0, 0.6, a, fc=C_BLUE_FILL, ec=C_PRIMARY, fs=9)
        ax.plot([x, x], [7.6, 0.4], color=C_GRAY, lw=1, ls="--", alpha=0.5)

    y = 7.3
    steps = [
        ("start(config)", xs[0], xs[1], C_PRIMARY),
        ("acquire asyncio.Lock", xs[1], xs[1], C_GREEN),
        ("Popen(['uv','run','python','main.py',...])", xs[1], xs[2], C_PRIMARY),
        ("status='running'", xs[2], xs[1], C_GRAY),
        ("初始化CDPBrowserManager", xs[2], xs[2], C_GREEN),
        ("pong() 登录态探活", xs[2], xs[3], C_ORANGE),
        ("selfinfo / localStorage校验", xs[3], xs[2], C_ORANGE),
        ("按模式采集(关键词/详情/创作者)", xs[2], xs[3], C_GREEN),
        ("分页 while <=MAX_NOTES_COUNT(15)", xs[2], xs[3], C_GREEN),
        ("Semaphore(1) 槽位控制", xs[2], xs[2], C_ORANGE),
        ("asyncio.sleep(2) 频率控制", xs[2], xs[2], C_ORANGE),
        ("返回原始内容列表", xs[3], xs[2], C_GREEN),
        ("构造 local_db_item(20字段)", xs[2], xs[2], C_PURPLE),
        ("store_content(item)", xs[2], xs[4], C_PRIMARY),
        ("content_is_exist(select)", xs[4], xs[4], C_ORANGE),
        ("exist? update : add (upsert)", xs[4], xs[4], C_GREEN),
        ("采集完成 poll()=0", xs[2], xs[1], C_PRIMARY),
        ("status='idle' 释放Lock", xs[1], xs[0], C_GRAY),
    ]
    for i, (label, x1, x2, color) in enumerate(steps):
        yy = y - i*0.4
        if x1 == x2:
            ax.add_patch(FancyArrowPatch((x1, yy+0.1), (x1, yy-0.1), arrowstyle="-|>",
                         mutation_scale=12, color=color, lw=1.6,
                         connectionstyle="arc3,rad=-0.6"))
            ax.text(x1+0.4, yy, label, fontsize=7.5, va="center", color=color)
        else:
            _arrow(ax, x1, yy, x2, yy, "", color, fs=7.5)
            ax.text((x1+x2)/2, yy+0.16, label, fontsize=7.5, ha="center", color=color)

    fig.savefig(OUT/"fig2_sequence.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============ 图3：登录态状态机图 ============
def diagram3_login_state():
    fig, ax = fig_setup(12, 7)
    ax.set_title("图3  登录态状态机", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    # 状态节点
    _box(ax, 1.0, 4.5, 2.2, 1.0, "未登录\n(初始)", fc=C_GRAY_FILL, ec=C_GRAY, fs=9)
    _box(ax, 4.5, 5.5, 2.5, 1.0, "登录中\n(login_by_*)", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=9)
    _box(ax, 8.5, 5.5, 2.5, 1.0, "登录态有效\n(profile缓存)", fc=C_GREEN_FILL, ec=C_GREEN, fs=9)
    _box(ax, 4.5, 3.2, 2.5, 1.0, "探活中\n(pong())", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=9)
    _box(ax, 1.0, 1.2, 2.2, 1.0, "登录态失效", fc=C_RED_FILL, ec=C_RED, fs=9)
    _box(ax, 4.5, 1.2, 2.5, 1.0, "更新中\n(Cookie注入)", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=9)
    _box(ax, 8.5, 1.2, 2.5, 1.0, "告警\n(人工介入)", fc=C_RED_FILL, ec=C_RED, fs=9)

    # 迁移
    _arrow(ax, 3.2, 4.8, 4.5, 5.9, "首次启动", C_PRIMARY, fs=8)
    _arrow(ax, 5.75, 5.5, 5.75, 4.2, "登录成功", C_GREEN, fs=8)
    _arrow(ax, 7.0, 6.0, 8.5, 6.0, "保存profile", C_GREEN, fs=8)
    _arrow(ax, 8.5, 5.7, 7.0, 4.0, "采集前探活", C_PRIMARY, fs=8)
    _arrow(ax, 5.75, 4.2, 5.75, 5.5, "有效→复用", C_GREEN, fs=8, offset=0.15)
    _arrow(ax, 4.5, 3.7, 3.2, 2.0, "探活失败", C_RED, fs=8)
    _arrow(ax, 3.2, 1.7, 4.5, 1.7, "触发更新", C_ORANGE, fs=8)
    _arrow(ax, 5.75, 2.2, 5.75, 3.2, "更新成功", C_GREEN, fs=8)
    _arrow(ax, 7.0, 1.7, 8.5, 1.7, "更新失败", C_RED, fs=8)
    _arrow(ax, 8.5, 2.2, 8.5, 5.5, "人工更新后\n重置", C_GRAY, fs=8, ls="--")

    fig.savefig(OUT/"fig3_login_state.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============ 图4：代理IP池架构图 ============
def diagram4_proxy_pool():
    fig, ax = fig_setup(12, 7)
    ax.set_title("图4  代理IP池架构", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    # 供应商层
    ax.text(2.0, 6.3, "供应商接入层", fontsize=10, fontweight="bold", color=C_SECOND, ha="center")
    _box(ax, 0.5, 5.2, 2.8, 0.8, "快代理\n(getdps API·需签名)", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=8.5)
    _box(ax, 0.5, 4.1, 2.8, 0.8, "豌豆HTTP\n(api·仅app_key)", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=8.5)
    _box(ax, 0.5, 3.0, 2.8, 0.8, "静态代理\n(STATIC_PROXY_URL)", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=8.5)

    # 池核心
    _box(ax, 4.2, 3.6, 3.6, 2.8, "", fc=C_GREEN_FILL, ec=C_GREEN, fs=9, lw=2)
    ax.text(6.0, 6.1, "ProxyIpPool", fontsize=10, fontweight="bold", color=C_GREEN, ha="center")
    _box(ax, 4.5, 5.2, 3.0, 0.6, "proxy_list: List[IpInfoModel]", fc="white", ec=C_GREEN, fs=8)
    _box(ax, 4.5, 4.4, 3.0, 0.6, "get_proxy()\nrandom.choice + remove", fc="white", ec=C_GREEN, fs=8)
    _box(ax, 4.5, 3.7, 3.0, 0.5, "_is_valid_proxy()\necho.apifox.cn 200校验", fc="white", ec=C_GREEN, fs=7.5)

    # 获取策略
    _arrow(ax, 3.3, 5.6, 4.2, 5.5, "get_proxy(n)", C_GRAY, fs=8)
    _arrow(ax, 3.3, 4.5, 4.2, 4.7, "", C_GRAY, fs=8)
    _arrow(ax, 3.3, 3.4, 4.2, 4.0, "", C_GRAY, fs=8)

    # 右侧刷新机制
    _box(ax, 8.8, 5.2, 2.8, 0.8, "ProxyRefreshMixin", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=9)
    _box(ax, 8.8, 4.1, 2.8, 0.8, "每次request前\n_refresh_proxy_if_expired", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=8)
    _box(ax, 8.8, 3.0, 2.8, 0.8, "is_expired(buffer=30s)\nget_or_refresh_proxy", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=8)
    _arrow(ax, 7.8, 4.7, 8.8, 4.5, "过期触发", C_ORANGE, fs=8)
    _arrow(ax, 8.8, 5.6, 7.8, 5.0, "重写proxy URL", C_GREEN, fs=8)

    # 底部特性
    _box(ax, 0.5, 1.2, 3.4, 1.0, "随机取+立即移除\n空则_reload_proxies", fc=C_PURPLE_FILL, ec=C_PURPLE, fs=8.5)
    _box(ax, 4.3, 1.2, 3.4, 1.0, "@retry(3次·间隔1s)\nget_proxy 重试", fc=C_PURPLE_FILL, ec=C_PURPLE, fs=8.5)
    _box(ax, 8.1, 1.2, 3.4, 1.0, "Redis缓存\n按provider_ip_port TTL", fc=C_PURPLE_FILL, ec=C_PURPLE, fs=8.5)

    fig.savefig(OUT/"fig4_proxy_pool.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============ 图5：数据归一化处理流程图 ============
def diagram5_normalize_flow():
    fig, ax = fig_setup(12, 8)
    ax.set_title("图5  数据归一化与存储处理流程", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    _box(ax, 4.2, 7.0, 3.6, 0.8, "原始数据\nnote_item: Dict", fc=C_GRAY_FILL, ec=C_GRAY, fs=9)
    _arrow(ax, 6, 7.0, 6, 6.5, "", C_GRAY)
    _box(ax, 3.7, 5.7, 4.6, 0.8, "字段映射适配器 update_xhs_note\n(抽 user_info/interact_info/image_list)", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=8.5)
    _arrow(ax, 6, 5.7, 6, 5.2, "", C_PRIMARY)
    _box(ax, 3.7, 4.4, 4.6, 0.8, "类型转换\nstr(count) · json.dumps(list) · ts→time", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=8.5)
    _arrow(ax, 6, 4.4, 6, 3.9, "注入source_keyword_var", C_PRIMARY, fs=8)
    _box(ax, 3.7, 3.1, 4.6, 0.8, "构造 local_db_item (20字段)\n含 source_keyword / xsec_token / note_url", fc=C_GREEN_FILL, ec=C_GREEN, fs=8.5)
    _arrow(ax, 6, 3.1, 6, 2.6, "", C_GREEN)
    _diamond(ax, 4.3, 1.5, 3.4, 1.0, "content_is_exist\n(select note_id)", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=8.5)
    # 分支
    _arrow(ax, 4.3, 2.0, 1.8, 2.6, "存在", C_GREEN, fs=8)
    _box(ax, 0.3, 2.6, 3.0, 0.8, "update_content\n仅更新count+last_modify_ts", fc=C_GREEN_FILL, ec=C_GREEN, fs=8)
    _arrow(ax, 7.7, 2.0, 10.2, 2.6, "不存在", C_PRIMARY, fs=8)
    _box(ax, 8.7, 2.6, 3.0, 0.8, "add_content\n新增完整记录", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=8)
    # 汇入
    _arrow(ax, 1.8, 3.4, 4.0, 4.2, "", C_GRAY, ls="--")
    _arrow(ax, 10.2, 3.4, 8.0, 4.2, "", C_GRAY, ls="--")
    _box(ax, 4.2, 0.2, 3.6, 0.8, "统一数据池 source_items\n(analysis_status=pending)", fc=C_RED_FILL, ec=C_RED, fs=9)
    _arrow(ax, 6, 1.5, 6, 1.0, "upsert 完成", C_RED, fs=8)

    fig.savefig(OUT/"fig5_normalize_flow.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============ 图6：任务调度状态图 ============
def diagram6_scheduler_state():
    fig, ax = fig_setup(12, 6.5)
    ax.set_title("图6  CrawlerManager 任务调度状态机", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    _box(ax, 0.8, 3.0, 2.0, 1.0, "idle\n(初始/完成)", fc=C_GRAY_FILL, ec=C_GRAY, fs=9)
    _box(ax, 4.0, 4.5, 2.2, 1.0, "running", fc=C_GREEN_FILL, ec=C_GREEN, fs=9)
    _box(ax, 4.0, 1.2, 2.2, 1.0, "stopping", fc=C_ORANGE_FILL, ec=C_ORANGE, fs=9)
    _box(ax, 8.0, 4.5, 2.0, 1.0, "error\n(启动失败)", fc=C_RED_FILL, ec=C_RED, fs=9)
    _box(ax, 8.0, 1.2, 2.6, 1.0, "completed\n(poll()=0)", fc=C_BLUE_FILL, ec=C_PRIMARY, fs=9)

    # 迁移
    _arrow(ax, 2.8, 3.7, 4.0, 4.7, "start()\nacquire Lock", C_GREEN, fs=8)
    _arrow(ax, 2.8, 3.3, 4.0, 1.7, "stop()", C_ORANGE, fs=8)
    _arrow(ax, 5.1, 4.5, 5.1, 2.2, "stop()\nSIGTERM", C_ORANGE, fs=8)
    _arrow(ax, 6.2, 4.8, 8.0, 5.0, "Popen失败", C_RED, fs=8)
    _arrow(ax, 6.2, 4.7, 8.0, 1.7, "_read_output\npoll()=0", C_PRIMARY, fs=8)
    _arrow(ax, 6.2, 1.7, 2.8, 3.3, "kill()\n释放", C_GRAY, fs=8, ls="--")
    _arrow(ax, 9.3, 2.2, 9.3, 4.5, "重置", C_GRAY, fs=8, ls="--")
    _arrow(ax, 8.0, 5.0, 2.8, 3.8, "return\n释放Lock", C_GRAY, fs=8, ls="--")

    # 关键约束标注
    _box(ax, 0.3, 0.1, 11.4, 0.7, "关键约束：asyncio.Lock 串行 · 无任务队列 · 并发start直接 return False · status=4值字面量(idle/running/stopping/error)",
         fc=C_RED_FILL, ec=C_RED, fs=8.5, rounded=False)

    fig.savefig(OUT/"fig6_scheduler_state.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============ 图7：反爬四层策略图 ============
def diagram7_anti_crawler():
    fig, ax = fig_setup(12, 7.5)
    ax.set_title("图7  反爬应对四层策略", fontsize=14, fontweight="bold", color=C_PRIMARY, pad=14)

    layers = [
        ("IP层", 6.0, C_RED_FILL, C_RED, [
            "代理IP池 (3供应商)", "random.choice+移除", "健康检查 echo.apifox.cn",
            "is_expired(buffer=30s)", "@retry(3次·1s)", "Redis缓存TTL"
        ]),
        ("指纹层", 4.5, C_ORANGE_FILL, C_ORANGE, [
            "CDP复用真实Chrome", "ENABLE_CDP_MODE=True", "profile持久化",
            "stealth脚本(仅标准模式)", "CDP下不注入stealth", "真实浏览器指纹"
        ]),
        ("频率层", 3.0, C_BLUE_FILL, C_PRIMARY, [
            "固定sleep(2s)", "asyncio.Semaphore(1)", "MAX_CONCURRENCY_NUM=1",
            "非随机间隔", "分页while上限15", "单帖评论上限10"
        ]),
        ("签名层", 1.5, C_GREEN_FILL, C_GREEN, [
            "抖音:PyExecJS·douyin.js", "知乎:PyExecJS·zhihu.js", "小红书:xhshow纯Python",
            "a_bogus参数注入", "x-zse-96/x-zst-81", "需Node.js环境(抖音/知乎)"
        ]),
    ]
    for name, y, fc, ec, items in layers:
        _layer(ax, 0.5, y, 11, 1.2, name, fc, ec, items, fs_title=9.5)

    fig.savefig(OUT/"fig7_anti_crawler.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    diagram1_architecture()
    diagram2_sequence()
    diagram3_login_state()
    diagram4_proxy_pool()
    diagram5_normalize_flow()
    diagram6_scheduler_state()
    diagram7_anti_crawler()
    print("7张图生成完成:", OUT)
    for f in sorted(OUT.glob("*.png")):
        print(" ", f.name)
