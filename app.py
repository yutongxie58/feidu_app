import streamlit as st
from datetime import datetime, timedelta, time as dtime
import json, csv, os

APP_TITLE = "费渡模拟器 · FeiDu v0.3（配置化 + 持久化）"
LOG_PATH = "feidu_logs.csv"
DATA_DIR = "data"  # 保存今日状态 data/YYYY-MM-DD.json
CONFIG_PATH = "routine.json"

# ---------------------------
# 细节清单（展示用，不计进度）
# ---------------------------
DETAILS = {
    "morning": [
        "关闹钟→坐起→喝温水 → 拉窗帘",
        "播放音乐/投影（舒醒 ≤30′）",
        "清晨学习：英语/理财/阅读（轻，不攻坚）",
        "晨间运动视频 ×25′（腹部/臀/手臂/拉伸）",
        "面部/下颌线 2–3′（舌顶上颚、抬头、轻拍）",
        "洗脸 → 爽肤水 → 精华 → 防晒",
        "早餐 + 维生素（蛋白+全谷+水果+咖啡）",
    ],
    "am": [
        "番茄 50/10 ×2–3（CS/算法/项目）",
        "每 2 个番茄远眺 + 走动 5′",
        "12:45 清理桌面→准备午休",
    ],
    "noon": [
        "喝酵素 → 关窗帘 → 午睡 20–25′",
        "起床即动：床上瘦臀腿/跑步机 10–20′（提神，不求强度）",
    ],
    "pm": [
        "继续 CS/论文/代码；每 90′ 起身走 5′",
        "17:30 收尾：写 3 句今日总结",
    ],
    "evening": [
        "18:00 晚餐（蛋白+蔬菜+少量主食；饭后走 10′ 或收拾 10′）",
        "自由：电影/剧/轻课程/日记/面膜",
        "21:45 洗脸 + 下颌线 + 护肤；周三/周日：洗澡洗头",
        "22:00 上床；手机远离；睡前拉伸/轻音乐 10′",
    ],
}

# ---------------------------
# 默认时段（当没 routine.json 时）
# ---------------------------
DEFAULT_BLOCKS = [
    {"key": "morning", "label": "早晨启动 (5:30–8:00)",  "start": "05:30", "end": "08:00", "enabled": True},
    {"key": "am",      "label": "上午专注 (8:00–13:00)", "start": "08:00", "end": "13:00", "enabled": True},
    {"key": "noon",    "label": "午间复苏 (13:00–14:00)","start": "13:00", "end": "14:00", "enabled": True},
    {"key": "pm",      "label": "下午冲刺 (14:00–18:00)","start": "14:00", "end": "18:00", "enabled": True},
    {"key": "evening", "label": "晚间自由 (18:00–22:00)","start": "18:00", "end": "22:00", "enabled": True},
]
DEFAULT_WEEK_RULES = {}

# ---------------------------
# 惩罚与进度参数
# ---------------------------
PROG_ON_START  = 10   # 每段开始 +10%
PROG_ON_FINISH = 10   # 每段结束 +10%
GRACE_MIN = 15                 # 到点后宽限 15 分钟未“开始” → 锁
OVERTIME_FINISH_GRACE_MIN = 10 # 段末后宽限 10 分钟未“结束” → 锁
LOCK_MIN  = 5                  # 锁定 5 分钟

# ---------------------------
# 工具函数
# ---------------------------
def now_dt() -> datetime:
    return datetime.now()

def today_date_str() -> str:
    return now_dt().date().isoformat()

def combine_today(t_hhmm: str) -> datetime:
    h, m = map(int, t_hhmm.split(":"))
    d = now_dt().date()
    return datetime(d.year, d.month, d.day, h, m, 0)

def seconds_left(dt_end: datetime) -> int:
    return max(0, int((dt_end - now_dt()).total_seconds()))

def write_log(event: str, label: str):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True) if os.path.dirname(LOG_PATH) else None
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "event", "label"])
        w.writerow([now_dt().isoformat(timespec='seconds'), event, label])

def read_config():
    # 读 routine.json；若没有则返回默认
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
            "started": b["started"],
            "finished": b["finished"],
            "start_time": b["start_time"].isoformat() if b["start_time"] else None,
            "finish_time": b["finish_time"].isoformat() if b["finish_time"] else None,
            "start_progress_awarded": b["start_progress_awarded"],
            "finish_progress_awarded": b["finish_progress_awarded"],
        })
    with open(os.path.join(DATA_DIR, f"{today_date_str()}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def try_restore_today_state():
    # 如果有当天文件，恢复进度和开始/结束标记
    path = os.path.join(DATA_DIR, f"{today_date_str()}.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state["progress"] = data.get("progress", 0)
        st.session_state["rest_mode"] = data.get("rest_mode", False)

        saved_by_key = {b["key"]: b for b in data.get("blocks", [])}
        for b in st.session_state["blocks"]:
            sb = saved_by_key.get(b["key"])
            if not sb:
                continue
            b["started"] = sb.get("started", False)
            b["finished"] = sb.get("finished", False)
            b["start_progress_awarded"] = sb.get("start_progress_awarded", False)
            b["finish_progress_awarded"] = sb.get("finish_progress_awarded", False)
            stime = sb.get("start_time")
            ftime = sb.get("finish_time")
            b["start_time"] = datetime.fromisoformat(stime) if stime else None
            b["finish_time"] = datetime.fromisoformat(ftime) if ftime else None
    except Exception:
        pass

def grace_deadline(block):    return block["start"] + timedelta(minutes=GRACE_MIN)
def overtime_deadline(block): return block["end"] + timedelta(minutes=OVERTIME_FINISH_GRACE_MIN)
def in_block(block):          return block["start"] <= now_dt() <= block["end"]
def before_block(block):      return now_dt() < block["start"]
def after_block(block):       return now_dt() > block["end"]

def add_progress(pct):
    st.session_state["progress"] = min(100, st.session_state["progress"] + pct)

def trigger_lock(reason: str, minutes: int = LOCK_MIN):
    # 休息日不惩罚
    if st.session_state.get("rest_mode"):
        return
    st.session_state["lock_until"] = now_dt() + timedelta(minutes=minutes)
    write_log(f"LOCK[{reason}] {minutes}m", "GLOBAL")
    save_today_state()

def is_locked():
    lu = st.session_state.get("lock_until")
    if not lu:
        return False
    if now_dt() >= lu:
        st.session_state["lock_until"] = None
        save_today_state()
        return False
    return True

def auto_refresh_every(seconds=30, key="auto_refresh"):
    """
    每隔 seconds 触发一次页面轻刷新，不会丢失 session 状态。
    """
    ts_key = f"{key}_ts"
    now = now_dt()
    last = st.session_state.get(ts_key)
    if last is None:
        st.session_state[ts_key] = now
    elif (now - last).total_seconds() >= seconds:
        st.session_state[ts_key] = now
        st.experimental_rerun()

# ---------------------------
# 状态初始化：读配置 + 当天状态
# ---------------------------
def ensure_state():
    if "config_loaded" not in st.session_state:
        blocks_cfg, week_rules, loaded = read_config()
        st.session_state["config_loaded"] = loaded
        st.session_state["week_rules"] = week_rules

        # 根据配置构造今天的 blocks
        st.session_state["blocks"] = []
        for c in blocks_cfg:
            if not c.get("enabled", True):
                continue
            st.session_state["blocks"].append({
                "key": c["key"],
                "label": c["label"],
                "start": combine_today(c["start"]),
                "end": combine_today(c["end"]),
                "started": False, "start_time": None,
                "finished": False, "finish_time": None,
                "start_progress_awarded": False,
                "finish_progress_awarded": False,
            })

    if "progress" not in st.session_state:
        st.session_state["progress"] = 0
    if "lock_until" not in st.session_state:
        st.session_state["lock_until"] = None
    if "rest_mode" not in st.session_state:
        st.session_state["rest_mode"] = False
    if "last_date" not in st.session_state:
        st.session_state["last_date"] = now_dt().date()

    # 跨天：重置并重新读配置
    if st.session_state["last_date"] != now_dt().date():
        st.session_state.clear()
        ensure_state()

    # 恢复今天的持久化状态（如有）
    try_restore_today_state()

# ---------------------------
# UI
# ---------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🕰️", layout="centered")
ensure_state()

st.title(APP_TITLE)
if st.session_state["config_loaded"]:
    st.caption("✅ 已加载 routine.json（可配置日程）")
else:
    st.caption("⚠️ 未找到 routine.json，使用内置默认日程")

# 顶部：休息日 + 清零
c1, c2, c3 = st.columns([3,2,2])

with c1:
    st.checkbox("🔕 今天是休息日（不打卡、不惩罚、仅浏览清单）", key="rest_mode")

with c2:
    if st.button("清零今日进度"):
        st.session_state["progress"] = 0
        st.session_state["lock_until"] = None
        for b in st.session_state["blocks"]:
            b["started"] = b["finished"] = False
            b["start_time"] = b["finish_time"] = None
            b["start_progress_awarded"] = b["finish_progress_awarded"] = False
        save_today_state()
        st.rerun()

with c3:
    if st.button("↻ 重载日程"):
        # 清掉配置相关缓存，下一次 ensure_state() 会重新读取 routine.json
        for k in ("config_loaded", "week_rules", "blocks"):
            if k in st.session_state:
                del st.session_state[k]
        # 不动进度和当天存档
        st.rerun()

# 进度条 & 时间
if st.session_state["rest_mode"]:
    st.progress(1.0, text="休息日")
else:
    st.progress(st.session_state["progress"]/100.0, text=f"今日进度：{st.session_state['progress']}%")
st.write(f"当前时间：**{now_dt().strftime('%H:%M:%S')}**")
auto_refresh_every(30)  # 每 30 秒自动刷新一次

# 锁定覆盖
if (not st.session_state["rest_mode"]) and is_locked():
    remaining = seconds_left(st.session_state["lock_until"])
    st.error(f"⛔ 锁定中（剩余 {remaining//60} 分 {remaining%60} 秒）。")
    st.stop()

# 顶部轻提醒：当前在段内但未开始
current_blocks = [b for b in st.session_state["blocks"] if b["start"] <= now_dt() <= b["end"]]
if current_blocks:
    b = current_blocks[0]
    if not b["started"] and not st.session_state.get(f"nudged_{b['key']}"):
        st.toast(f"现在是『{b['label']}』，点“开始打卡”吧。", icon="⏰")
        st.session_state[f"nudged_{b['key']}"] = True

# 渲染各段
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

    # 休息日：只展示清单
    if st.session_state["rest_mode"]:
        st.caption("休息日：本时段不需打卡。")
        continue

    weekday_iso = now_dt().isoweekday()
    rules_today = st.session_state.get("week_rules", {}).get(str(weekday_iso), {})
    rule_for_this = rules_today.get(block["key"], {})
    note = rule_for_this.get("note")
    if note:
        st.caption(f"🗓️ 今日规则：{note}")

    # 状态文本
    tags = []
    if block["started"]: tags.append("已开始")
    if block["finished"]: tags.append("已结束")
    st.write("状态：" + (" / ".join(tags) if tags else "未打卡"))

    # 惩罚自动检查
    if in_block(block):
        if not block["started"] and now_dt() > grace_deadline(block):
            trigger_lock(reason=f"no-start: {block['label']}")
            st.rerun()
        if block["started"] and (not block["finished"]) and now_dt() > overtime_deadline(block):
            trigger_lock(reason=f"no-finish: {block['label']}")
            st.rerun()

    # 操作按钮
    cA, cB, cC = st.columns([1,1,2])
    with cA:
        if st.button("开始打卡", key=f"start_{idx}", disabled=block["started"] or after_block(block)):
            if before_block(block):
                st.warning("未到时间，不能开始。")
            else:
                block["started"] = True
                block["start_time"] = now_dt()
                write_log("START", block["label"])
                if not block["start_progress_awarded"]:
                    add_progress(PROG_ON_START)
                    block["start_progress_awarded"] = True
                save_today_state()
                st.rerun()
    with cB:
        if st.button("结束打卡", key=f"finish_{idx}", disabled=(not block["started"]) or block["finished"]):
            if not block["started"]:
                st.error("你还没有开始。")
            else:
                if now_dt() > overtime_deadline(block):
                    trigger_lock(reason=f"late-finish: {block['label']}")
                    st.rerun()
                block["finished"] = True
                block["finish_time"] = now_dt()
                write_log("FINISH", block["label"])
                if not block["finish_progress_awarded"]:
                    add_progress(PROG_ON_FINISH)
                    block["finish_progress_awarded"] = True
                save_today_state()
                st.rerun()
    with cC:
        if st.button("我卡住了", key=f"stuck_{idx}"):
            st.session_state["lock_until"] = now_dt() + timedelta(seconds=60)
            write_log("SOFT_LOCK(I'm stuck)", block["label"])
            save_today_state()
            st.rerun()
