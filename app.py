import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
import json, csv, os, time, base64, mimetypes, uuid
from typing import Optional

try:
    _rerun = st.rerun
except AttributeError:
    _rerun = st.experimental_rerun

# ========= 基本信息 =========
TZ = ZoneInfo("America/Los_Angeles")
APP_TITLE   = "费渡模拟器 · FeiDu v0.3（配置化 + 持久化 + 时区修正）"
LOG_PATH    = "feidu_logs.csv"
DATA_DIR    = "data"            # 保存今日状态 data/YYYY-MM-DD.json
CONFIG_PATH = "routine.json"    # 可配置日程
SIMPLE_CHECKIN = True           # 点击“开始打卡”=该段直接完成

HAS_DIALOG = hasattr(st, "dialog")  # 兼容老版本 Streamlit 弹窗

# ========= 媒体与资产 =========
MEDIA_DIR = "media"
ASSET_DIR = "assets"
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(ASSET_DIR, exist_ok=True)
BG_PATH = os.path.join(ASSET_DIR, "background.jpg")
GLOBAL_NUDGE_PATH = os.path.join(ASSET_DIR, "nudge.mp4")

# ========= 细节清单（展示用，不计进度）=========
DETAILS = {
    "wake": [
        "关闹钟 → 坐起 30s → 双臂上举伸展 3×10s",
        "喝一杯温水（200–300ml）",
        "拉开窗帘/开窗透气 1–2min",
        "慢醒模式：听歌/投影治愈片 ≤30min（别躺回去）",
        "烧水/准备咖啡器具（法压/手冲随意）"
    ],
    "breakfast": [
        "早餐搭配：蛋白（蛋/酸奶/鸡胸）+ 全谷（燕麦/全麦）+ 水果",
        "咖啡/热茶一杯（避免空腹过多咖啡）",
        "维生素/鱼油（如有）随餐",
        "快速清理台面 2min → 桌面进入学习状态"
    ],
    "morning_study": [
        "Anything Zone：英语听力/单词、理财/股票入门、阅读/写总结（轻，不攻坚）",
        "定闹钟 25–30min × 2–3 轮（短番茄）",
        "每轮后肩颈伸展 1–2min",
        "记录 1 条“今天要完成的最小成果”（一句话）"
    ],
    "morning_exercise": [
        "热身 3min：开合跳 30s → 猫牛式 10次 → 髋环绕 10次/侧",
        "主训 20min（跟视频）：核心/臀/上肢混合 3 轮",
        "放松 2–3min：股四头/小腿/臀外侧拉伸",
        "面部/下颌线激活 2–3min：舌顶上颚 1′ → 抬头前伸 10s×3 → 轻拍下颌 30s",
        "护肤：洗脸 → 爽肤水 → 精华 → 防晒"
    ],
    "am": [
        "主学习（10:00–13:00）：CS/算法/项目推进",
        "番茄 50/10（两轮后远眺 1–2min）",
        "手机远离桌面（抽屉/另一房间）",
        "12:45 收尾：整理代码/笔记 → 写下午目标"
    ],
    "noon": [
        "喝酵素/清水 → 关窗帘 → 午睡 20–25min（定闹钟）",
        "起床即动（提神而非训练）：",
        "  · 床上瘦腿/臀 10–15min：抬腿15×2｜内夹腿15×2｜自行车30s×2",
        "  · 或 跑步机 10–20min 快走/小跑 + 轻拉伸",
        "补水 200ml"
    ],
    "pm": [
        "学术专注（14:00–18:00）：CS/论文/编码",
        "每 90min 起身走 5min（倒咖啡/热茶）",
        "遇到卡点：改环境（换位置/戴耳塞/听白噪音）",
        "17:30 收尾：写 3 句今日总结（问题/进展/明日第一步）"
    ],
    "evening": [
        "18:00 晚餐：蛋白 + 蔬菜 + 少量主食（七分饱）",
        "饭后 10min：散步或收拾台面",
        "自由区（19:00–22:00）：电影/剧/轻课程/感恩日记/面膜",
        "21:45 洗脸 + 下颌线 + 护肤；（周三/周日）洗澡洗头 → 护肤 → 吹干",
        "22:00 上床：手机远离 → 轻音乐/呼吸 10min → 入睡"
    ]
}

# ========= 默认时段（当没 routine.json 时使用）=========
DEFAULT_BLOCKS = [
    {"key": "wake",             "label": "起床 (5:30–6:00)",              "start": "05:30", "end": "06:00", "enabled": True},
    {"key": "breakfast",        "label": "早餐 (6:00–7:00)",               "start": "06:00", "end": "07:00", "enabled": True},
    {"key": "morning_study",    "label": "清晨学习 (7:00–9:00)",           "start": "07:00", "end": "09:00", "enabled": True},
    {"key": "morning_exercise", "label": "晨间运动 + 护肤 (9:00–10:00)",   "start": "09:00", "end": "10:00", "enabled": True},
    {"key": "am",               "label": "上午专注 (10:00–13:00)",         "start": "10:00", "end": "13:00", "enabled": True},
    {"key": "noon",             "label": "午间复苏 (13:00–14:00)",         "start": "13:00", "end": "14:00", "enabled": True},
    {"key": "pm",               "label": "下午冲刺 (14:00–18:00)",         "start": "14:00", "end": "18:00", "enabled": True},
    {"key": "evening",          "label": "晚间自由 (18:00–22:00)",         "start": "18:00", "end": "22:00", "enabled": True},
]
DEFAULT_WEEK_RULES = {
    "3": {"evening": {"note": "今晚记得洗澡 ✔"}},
    "7": {"evening": {"note": "今晚记得洗澡 ✔"}}
}

# ========= 工具函数 =========
def now_dt() -> datetime:
    return datetime.now(TZ)

def today_date_str() -> str:
    return now_dt().date().isoformat()

def combine_today(t_hhmm: str) -> datetime:
    h, m = map(int, t_hhmm.split(":"))
    d = now_dt().date()
    return datetime(d.year, d.month, d.day, h, m, 0, tzinfo=TZ)

def write_log(event: str, label: str):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True) if os.path.dirname(LOG_PATH) else None
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "event", "label"])
        w.writerow([now_dt().isoformat(timespec='seconds'), event, label])

def read_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            blocks = [b for b in cfg.get("blocks", []) if b.get("enabled", True)]
            week_rules = cfg.get("week_rules", {})
            return blocks, week_rules, True
        except Exception:
            pass
    return DEFAULT_BLOCKS, DEFAULT_WEEK_RULES, False

def save_today_state():
    os.makedirs(DATA_DIR, exist_ok=True)
    out = {
        "date": today_date_str(),
        "progress": st.session_state["progress"],
        "rest_mode": st.session_state["rest_mode"],
        "blocks": []
    }
    for b in st.session_state["blocks"]:
        out["blocks"].append({
            "key": b["key"],
            "label": b["label"],
            "start": b["start"].isoformat(),
            "end": b["end"].isoformat(),
            "started": b.get("started", False),
            "finished": b.get("finished", False),
            "start_time": b.get("start_time").isoformat() if b.get("start_time") else None,
            "finish_time": b.get("finish_time").isoformat() if b.get("finish_time") else None,
        })
    with open(os.path.join(DATA_DIR, f"{today_date_str()}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def try_restore_today_state():
    path = os.path.join(DATA_DIR, f"{today_date_str()}.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state["progress"]  = data.get("progress", 0)
        st.session_state["rest_mode"] = data.get("rest_mode", False)
        saved_by_key = {b["key"]: b for b in data.get("blocks", [])}
        for b in st.session_state["blocks"]:
            sb = saved_by_key.get(b["key"])
            if not sb:
                continue
            b["started"]  = sb.get("started", False)
            b["finished"] = sb.get("finished", False)
            stime = sb.get("start_time")
            ftime = sb.get("finish_time")
            b["start_time"]  = datetime.fromisoformat(stime) if stime else None
            b["finish_time"] = datetime.fromisoformat(ftime) if ftime else None
    except Exception:
        pass

def in_block(block):     return block["start"] <= now_dt() <= block["end"]
def before_block(block): return now_dt() <  block["start"]
def after_block(block):  return now_dt() >  block["end"]

def animate_progress_to(target: int, duration=0.8, steps=32):
    target = max(0, min(100, int(target)))
    cur = int(st.session_state.get("progress", 0))
    if target <= cur:
        st.session_state["progress"] = target
        return
    delta = target - cur
    sleep = duration / steps
    for i in range(1, steps + 1):
        st.session_state["progress"] = cur + int(delta * i / steps)
        st.session_state["_progress_needs_render"] = True
        time.sleep(sleep)

def set_background_from_file(path: str):
    if not os.path.exists(path):
        return
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .block-container {{ backdrop-filter: blur(1px); }}
        </style>
        """,
        unsafe_allow_html=True
    )

def video_file_to_data_uri(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "video/mp4"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"

def open_nudge_for(block_key: str):
    """只打开某个时段的nudge，其他时段的nudge全部关闭。"""
    for b in st.session_state.get("blocks", []):
        st.session_state.pop(f"show_local_nudge_{b['key']}", None)
    st.session_state[f"show_local_nudge_{block_key}"] = True

def close_nudge_for(block_key: str):
    st.session_state.pop(f"show_local_nudge_{block_key}", None)
    # 若你还有旧的全局弹窗标记，一并关掉（防守式）
    st.session_state["show_nudge"] = False

# ========= 状态初始化 =========
def ensure_state():
    if "config_loaded" not in st.session_state:
        blocks_cfg, week_rules, loaded = read_config()
        st.session_state["config_loaded"] = loaded
        st.session_state["week_rules"] = week_rules

        st.session_state["blocks"] = []
        for c in blocks_cfg:
            if not c.get("enabled", True):
                continue
            st.session_state["blocks"].append({
                "key": c["key"],
                "label": c["label"],
                "start": combine_today(c["start"]),
                "end":   combine_today(c["end"]),
                "started": False, "start_time": None,
                "finished": False, "finish_time": None
            })

    if "progress" not in st.session_state:
        st.session_state["progress"] = 0
    if "rest_mode" not in st.session_state:
        st.session_state["rest_mode"] = False
    if "last_date" not in st.session_state:
        st.session_state["last_date"] = now_dt().date()

    if st.session_state["last_date"] != now_dt().date():
        st.session_state.clear()
        ensure_state()

    try_restore_today_state()

    if SIMPLE_CHECKIN:
        n = len(st.session_state["blocks"])
        st.session_state["per_block_award"] = round(100 / n, 2) if n else 0
    else:
        st.session_state["per_block_award"] = 10

# ========= UI =========
st.set_page_config(page_title=APP_TITLE, page_icon="🕰️", layout="centered")
ensure_state()

st.title(APP_TITLE)
if os.path.exists(BG_PATH):
    set_background_from_file(BG_PATH)

# 配置加载提示
if st.session_state["config_loaded"]:
    st.caption("✅ 已加载 routine.json（可配置日程）")
else:
    st.caption("⚠️ 未找到 routine.json，使用内置默认日程")

# 顶部：休息日 + 清零 + 重载日程
c1, c2, c3 = st.columns([3,2,2])

with c1:
    # 用不同的 key，避免和 st.session_state["rest_mode"] 冲突
    rest_checked = st.checkbox("🔕 今天是休息日（只显示休息页）",
                               value=st.session_state.get("rest_mode", False),
                               key="rest_mode_checkbox")
    # 明确同步到逻辑用的 state 键
    st.session_state["rest_mode"] = bool(rest_checked)

with c2:
    if st.button("清零今日进度"):
        st.session_state["progress"] = 0
        for b in st.session_state["blocks"]:
            b["started"] = b["finished"] = False
            b["start_time"] = b["finish_time"] = None
        save_today_state()
        st.rerun()

with c3:
    if st.button("↻ 重载日程"):
        for k in ("config_loaded", "week_rules", "blocks"):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# —— 休息日纯页面（仅背景+提示） ——
if st.session_state.get("rest_mode", False):
    # 勾选立刻持久化，保证刷新后还是休息页
    save_today_state()

    st.markdown("""
        <div style="height:65vh;display:flex;align-items:center;justify-content:center;">
            <div style="text-align:center;background:rgba(255,255,255,0.25);padding:24px 32px;border-radius:16px;backdrop-filter:blur(2px);">
                <h1 style="margin:0 0 8px 0;">🛌 休息日</h1>
                <p style="margin:0;">放过自己一下。散步、晒太阳、看一部喜欢的电影也不错。</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 注意：先改状态、先保存，再触发重跑
    if st.button("结束休息，回到今日视图"):
        st.session_state["rest_mode"] = False
        save_today_state()
        _rerun()  # 你上面定义的 fallback: st.rerun 或 st.experimental_rerun

    st.stop()

# 进度条 & 当前时间
bar = st.progress(st.session_state["progress"]/100.0, text=f"今日进度：{st.session_state['progress']}%")
st.write(f"当前时间：**{now_dt().strftime('%H:%M:%S')}**")

# 自动刷新（30s）
def auto_refresh_every(seconds=30, key="auto_refresh"):
    ts_key = f"{key}_ts"
    now = now_dt()
    last = st.session_state.get(ts_key)
    if last is None:
        st.session_state[ts_key] = now
    elif (now - last).total_seconds() >= seconds:
        st.session_state[ts_key] = now
        st.rerun()
auto_refresh_every(30)

# ========= 渲染各段 =========
for idx, block in enumerate(st.session_state["blocks"]):
    st.divider()
    st.subheader(block["label"])
    col1, col2, col3 = st.columns(3)
    with col1: st.write(f"开始：{block['start'].strftime('%H:%M')}")
    with col2: st.write(f"结束：{block['end'].strftime('%H:%M')}")
    with col3:
        if in_block(block): st.success("进行中")
        elif before_block(block): st.info("未开始")
        else: st.write("已过期")

    # 细节清单（默认展开）
    dkey = block["key"]
    if dkey in DETAILS:
        with st.expander("细节清单（可打勾，纯引导）", expanded=True):
            for j, item in enumerate(DETAILS[dkey]):
                st.checkbox(item, key=f"sub_{dkey}_{j}")

    # 周规则提示（routine.json 可选）
    weekday_iso = now_dt().isoweekday()
    rules_today = st.session_state.get("week_rules", {}).get(str(weekday_iso), {})
    note = rules_today.get(block["key"], {}).get("note")
    if note:
        st.caption(f"🗓️ 今日规则：{note}")

    # 状态
    tags = []
    if block["started"]: tags.append("已打卡")
    st.write("状态：" + (" / ".join(tags) if tags else "未打卡"))

    # —— 操作按钮（开始=完成 + 不想动）——
    cA, cC = st.columns([1,2])

    with cA:
        if st.button("开始打卡", key=f"start_{idx}", disabled=block["started"] or after_block(block)):
            if before_block(block):
                st.warning("未到时间，不能开始。")
            else:
                block["started"] = True
                block["start_time"] = now_dt()
                block["finished"] = True
                block["finish_time"] = now_dt()
                write_log("START", block["label"])
                write_log("FINISH(AUTO_BY_SIMPLE)", block["label"])

                # 进度动画：按段平均
                per = st.session_state.get("per_block_award", 0)
                target = min(100, int(st.session_state["progress"] + per))
                animate_progress_to(target, duration=0.8, steps=32)

                # ✅ 关键：开始后，关闭该时段的 nudge 播放器
                close_nudge_for(block["key"])

                save_today_state()
                _rerun()

    with cC:
        # 只在“当前时段”展示
        if in_block(block):
            if st.button("不想动？", key=f"nudge_play_{block['key']}"):
                # ✅ 打开该时段的 nudge（并自动关闭其它时段的）
                open_nudge_for(block["key"])
                _rerun()
    
    # --- 嵌入式 nudge 播放器（直到点“开始打卡”才关闭）---
    if st.session_state.get(f"show_local_nudge_{block['key']}", False) and os.path.exists(GLOBAL_NUDGE_PATH):
        src = video_file_to_data_uri(GLOBAL_NUDGE_PATH)
        if src:
            st.markdown(
                f"""
                <video src="{src}" autoplay loop muted playsinline controls
                    style="width:100%;border-radius:12px;margin-top:8px"></video>
                """,
                unsafe_allow_html=True
            )
        else:
            # 回退：由 streamlit 托管（不能保证自动播放）
            st.video(GLOBAL_NUDGE_PATH)
        st.caption("准备好就点上面的「开始打卡」，视频会自动收起。")

# ========= 页面底部 · 自定义（背景 & 全局视频）=========
with st.expander("⚙️ 自定义（背景 & 全局『不想动』视频）", expanded=False):
    st.subheader("🖼 背景图片")
    bg = st.file_uploader("选择一张背景图片（jpg/png）", type=["jpg", "jpeg", "png"], key="bg_up")
    colbg1, colbg2 = st.columns(2)
    with colbg1:
        if bg and st.button("设为背景", use_container_width=True):
            with open(BG_PATH, "wb") as f:
                f.write(bg.getbuffer())
            st.success("背景已更新")
            st.rerun()
    with colbg2:
        if os.path.exists(BG_PATH) and st.button("移除背景", use_container_width=True):
            os.remove(BG_PATH)
            st.success("已移除背景")
            st.rerun()

    st.markdown("---")
    st.subheader("🎬 全局『不想动』视频")
    up = st.file_uploader("选择一个 mp4/mov/webm 视频作为全局激励视频", type=["mp4","mov","m4v","webm"], key="global_nudge_up")
    c1, c2 = st.columns(2)
    with c1:
        if up and st.button("保存为全局视频", use_container_width=True):
            with open(GLOBAL_NUDGE_PATH, "wb") as f:
                f.write(up.getbuffer())
            st.success("全局视频已更新")
            st.rerun()
    with c2:
        if os.path.exists(GLOBAL_NUDGE_PATH) and st.button("移除全局视频", use_container_width=True):
            os.remove(GLOBAL_NUDGE_PATH)
            st.success("已移除全局视频")
            st.rerun()
    if os.path.exists(GLOBAL_NUDGE_PATH):
        st.caption("预览：")
        st.video(GLOBAL_NUDGE_PATH)
