# memos-graph Viewer UI Design v0.1

> **目的**：v0.1 Viewer 3 页面的设计（不实装，只 wireframe + 路由 + 数据契约）
> **关联**：DESIGN §7 / SPEC §0.1 P0.12 / TASK_BREAKDOWN T13
> **技术栈**：FastAPI + Jinja2 + 原生 HTML/CSS/JS（**不引前端框架**）

---

## 0. 设计原则

1. **无 JS 框架**：vanilla JS + Fetch API，3 页面 < 200KB 资源
2. **CSS 原生变量**：light/dark 模式切换
3. **服务端渲染**：Jinja2 模板首屏 HTML，JS 只做增量更新
4. **响应式**：≥ 1024px 桌面优先，手机能看（不优化）
5. **无登录**：localhost only

---

## 1. 全局布局

```
┌─────────────────────────────────────────────────────┐
│  🧠 memos-graph                          [⚙] [?]   │  <- Top bar (50px)
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│ Sidebar  │  Main Content                            │
│ (200px)  │                                          │
│          │                                          │
│ Dashboard│                                          │
│ State    │                                          │
│ Timeline │                                          │
│ Promises │                                          │
│ Packs    │                                          │
│ System   │                                          │
│          │                                          │
└──────────┴──────────────────────────────────────────┘
```

**Sidebar** 静态（v0.1 不折叠、不路由跳）  
**Top bar** 固定，右上角：齿轮（设置，跳 `/api/v1/config` JSON 视图）、问号（跳 docs）  
**Main content** 按 sidebar 选的项目渲染

---

## 2. 路由

### 2.1 v0.1 必出（4 页面 + 静态资源 + 错误页）

| 路径 | 页面 | 模板 |
|------|------|------|
| `GET /` | Dashboard 摘要 | `dashboard.html` |
| `GET /state/{agent_id}` | Agent 状态面板 | `state.html` |
| `GET /timeline/{agent_id}` | Event 时间线 | `timeline.html` |
| `GET /promises/{agent_id}` | 承诺看板 | `promises.html` |
| `GET /static/*` | 静态资源 | (FastAPI StaticFiles) |
| `GET /coming-soon` | v0.2 路由 fallback | `coming_soon.html` |
| `GET /404` | 任意 404 | `404.html` |

### 2.2 v0.2 推迟（**侧栏链接到 /coming-soon，禁 404**）

| 路径 | 页面 | v0.1 行为 |
|------|------|----------|
| `GET /packs` | Pack 列表 | 重定向到 `/coming-soon?path=/packs` |
| `GET /packs/{id}` | Pack 详情 | 重定向到 `/coming-soon?path=/packs/{id}` |
| `GET /system` | 系统健康 | 重定向到 `/coming-soon?path=/system` |
| `GET /config` | 配置 UI | 重定向到 `/coming-soon?path=/config` |

**实现**：
```python
V0_2_PATHS = {"/packs", "/system", "/config"}
@router.get("/{path:path}")
async def fallback(path: str):
    if path in V0_2_PATHS or path.startswith("packs/"):
        return RedirectResponse(f"/coming-soon?path=/{path}")
    raise HTTPException(404, "Not Found", templates.TemplateResponse("404.html", ...))
```

---

## 3. 页面 1: Dashboard (`/`)

### 3.1 Wireframe

```
┌─────────────────────────────────────────────────────┐
│  📊 Dashboard                                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─ Total Chunks ─┐  ┌─ Total Events ─┐  ┌─ Packs ─┐│
│  │     12,453      │  │    156,789     │  │   3    ││
│  │  +234 today     │  │  +1,203 today  │  │ enabled││
│  └─────────────────┘  └────────────────┘  └────────┘│
│                                                      │
│  ┌─ Recall P50 ────┐  ┌─ Uptime ──────┐  ┌─ Disk ──┐│
│  │    142ms        │  │   3d 5h       │  │  42%   ││
│  │  target: <300ms │  │  since boot   │  │ 84GB/200││
│  └─────────────────┘  └────────────────┘  └────────┘│
│                                                      │
│  ┌─ Recent Agents (last 5 interactions) ────────────┐│
│  │ nako        2 min ago   stage 2  affinity 65     ││
│  │ work-coder  15 min ago  stage 1  affinity 12     ││
│  │ ...                                              ││
│  └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### 3.2 数据契约

```python
# viewer/server.py: GET /
@router.get("/")
async def dashboard():
    return {
        "stats": {
            "total_chunks": await db.scalar("SELECT COUNT(*) FROM chunks"),
            "chunks_today": await db.scalar("SELECT COUNT(*) FROM chunks WHERE created_at > now() - interval '1 day'"),
            "total_events": ...,
            "events_today": ...,
            "packs_enabled": ...,
            "uptime_seconds": ...,
            "disk_percent": ...,
            "recall_p50_ms": ...,  # from prometheus metric
        },
        "recent_agents": [
            {
                "agent_id": "nako",
                "last_interaction": "2026-07-02T11:28:00Z",
                "stage": 2,
                "affinity": 65,
            },
            ...
        ],
    }
```

### 3.3 模板变量

```html
<!-- dashboard.html -->
<h1>📊 Dashboard</h1>
<div class="cards">
  <div class="card">Total Chunks: {{ stats.total_chunks }}</div>
  ...
</div>
<table class="recent-agents">
  {% for a in recent_agents %}
  <tr>
    <td><a href="/state/{{ a.agent_id }}">{{ a.agent_id }}</a></td>
    <td>{{ a.last_interaction | relative_time }}</td>
    <td>stage {{ a.stage }}</td>
    <td>affinity {{ a.affinity }}</td>
  </tr>
  {% endfor %}
</table>
```

---

## 4. 页面 2: Agent State (`/state/{agent_id}`)

### 4.1 Wireframe

```
┌─────────────────────────────────────────────────────┐
│  🤖 nako                              [refresh]    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─ Identity ──────┐  ┌─ Stats ────────────────────┐│
│  │ pack: nako      │  │ Stage:       2 / 5        ││
│  │ runtime: openclaw│ │ Affinity:   65 / 100      ││
│  │ enabled:   ✓    │  │ Mood:       70 / 100      ││
│  │ version:  0.3.0 │  │ Energy:     60 / 100      ││
│  └─────────────────┘  │ Last seen:  2 min ago     ││
│                       └────────────────────────────┘│
│                                                      │
│  ┌─ Mood Trend (last 7 days) ───────────────────────┐│
│  │ ▁▂▃▅▆▇█▇▆▅▄▃▂▁  (SVG line chart)               ││
│  └──────────────────────────────────────────────────┘│
│                                                      │
│  ┌─ Quick Actions ──────────────────────────────────┐│
│  │ [Trigger Heartbeat]  [Open Timeline]             ││
│  │ [Open Promises]      [Reinstall Pack]            ││
│  └──────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### 4.2 数据契约

```python
@router.get("/state/{agent_id}")
async def state_page(agent_id: str):
    return {
        "identity": {
            "agent_id": agent_id,
            "pack_id": ...,
            "runtime": ...,
            "pack_version": ...,
            "enabled": ...,
        },
        "stats": {
            "stage": ...,
            "affinity": ...,
            "mood": ...,
            "energy": ...,
            "last_interaction": ...,
            "last_heartbeat": ...,
            "version": ...,  # 乐观锁
        },
        "mood_trend": [
            {"date": "2026-06-26", "mood": 60},
            ...
        ],
        "actions": {
            "trigger_heartbeat_url": f"/api/v1/agents/{agent_id}/heartbeat",
            "timeline_url": f"/timeline/{agent_id}",
            "promises_url": f"/promises/{agent_id}",
        },
    }
```

### 4.3 模板

```html
<!-- state.html -->
<h1>🤖 {{ identity.agent_id }}</h1>
<div class="identity">
  pack: <code>{{ identity.pack_id }}</code> ·
  runtime: <code>{{ identity.runtime }}</code> ·
  version: <code>{{ identity.pack_version }}</code>
</div>
<div class="stats">
  Stage: <span class="badge">{{ stats.stage }}</span>
  Affinity: <progress value="{{ stats.affinity }}" max="100"></progress> {{ stats.affinity }}%
  ...
</div>
<svg id="mood-chart" data-points="{{ mood_trend | tojson }}"></svg>
<!-- JS: 渲染折线图（v0.1 用纯 SVG path，不用 chart.js） -->
<div class="actions">
  <button onclick="fetch('{{ actions.trigger_heartbeat_url }}', {method:'POST'})">
    Trigger Heartbeat
  </button>
  ...
</div>
```

---

## 5. 页面 3: Timeline (`/timeline/{agent_id}`)

### 5.1 Wireframe

```
┌─────────────────────────────────────────────────────┐
│  📅 Timeline — nako                  [filter ▾]    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  2026-07-02                                          │
│  ┌──────────────────────────────────────────────┐  │
│  │ 11:28  💬 message      user: 早安             │  │
│  │ 11:30  🎯 mood_change  mood: 50→70           │  │
│  │ 11:35  💬 message      agent: 主人早~        │  │
│  │ 11:40  📌 promise      "做蛋糕" due 07-04   │  │
│  │ ...                                          │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  2026-07-01                                          │
│  ┌──────────────────────────────────────────────┐  │
│  │ 23:15  ❤️ heartbeat   stage 2, 8h idle       │  │
│  │ ...                                          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 5.2 数据契约

```python
@router.get("/timeline/{agent_id}")
async def timeline_page(agent_id: str, type: str = None, days: int = 7):
    return {
        "agent_id": agent_id,
        "filter_type": type,  # message|heartbeat|mood_change|promise|...
        "days": days,
        "events_by_date": [
            {
                "date": "2026-07-02",
                "events": [
                    {
                        "id": 12345,
                        "time": "11:28:00",
                        "type": "message",
                        "actor": "user",
                        "summary": "早安",
                        "icon": "💬",
                        "color": "#3b82f6",
                    },
                    ...
                ],
            },
            ...
        ],
    }
```

### 5.3 模板

```html
<!-- timeline.html -->
<h1>📅 Timeline — {{ agent_id }}</h1>
<form class="filters">
  <select name="type" onchange="this.form.submit()">
    <option value="">All</option>
    <option value="message">💬 Messages</option>
    <option value="heartbeat">❤️ Heartbeats</option>
    <option value="mood_change">🎯 Mood</option>
    ...
  </select>
  <select name="days">
    <option value="1">Today</option>
    <option value="7" selected>Last 7 days</option>
    <option value="30">Last 30 days</option>
  </select>
</form>
{% for day in events_by_date %}
  <h2>{{ day.date }}</h2>
  {% for e in day.events %}
  <div class="event" style="border-left: 3px solid {{ e.color }}">
    <span class="time">{{ e.time }}</span>
    <span class="icon">{{ e.icon }}</span>
    <span class="actor">{{ e.actor }}</span>
    <span class="summary">{{ e.summary }}</span>
  </div>
  {% endfor %}
{% endfor %}
```

---

## 6. 页面 4: Promises (`/promises/{agent_id}`)

### 6.1 Wireframe

```
┌─────────────────────────────────────────────────────┐
│  📌 Promises — nako                  [+ new]        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  🔴 Open (Due soon)                                  │
│  ┌──────────────────────────────────────────────┐  │
│  │ "周末做蛋糕"                                 │  │
│  │ created 2026-06-30  due 2026-07-05 (3d)    │  │
│  │ [✓ fulfilled]  [✗ broken]  [↻ extend]       │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  🟡 Open (no deadline)                              │
│  ┌──────────────────────────────────────────────┐  │
│  │ "学吉他"                                    │  │
│  │ created 2026-06-15  no due                  │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ✅ Fulfilled (recent)                               │
│  ┌──────────────────────────────────────────────┐  │
│  │ "买猫粮"  fulfilled 2026-06-28              │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 6.2 数据契约

```python
@router.get("/promises/{agent_id}")
async def promises_page(agent_id: str):
    return {
        "agent_id": agent_id,
        "due_soon": [
            {
                "id": 1,
                "content": "周末做蛋糕",
                "created_at": "2026-06-30T10:00:00Z",
                "due_at": "2026-07-05T23:59:59Z",
                "days_remaining": 3,
                "urgency": "high",  # < 24h = high, < 7d = medium
            },
            ...
        ],
        "open_no_deadline": [...],
        "fulfilled_recent": [...],
    }
```

### 6.3 模板

```html
<!-- promises.html -->
<h1>📌 Promises — {{ agent_id }}</h1>
<button class="new">+ New promise</button>
<!-- (new promise form via modal, v0.1 可选) -->

<h2>🔴 Open (Due soon)</h2>
{% for p in due_soon %}
<div class="promise urgency-{{ p.urgency }}">
  <p>"{{ p.content }}"</p>
  <small>created {{ p.created_at }} due {{ p.due_at }} ({{ p.days_remaining }}d)</small>
  <div class="actions">
    <button onclick="markFulfilled({{ p.id }})">✓ fulfilled</button>
    <button onclick="markBroken({{ p.id }})">✗ broken</button>
  </div>
</div>
{% endfor %}
...
```

### 6.4 颜色规则

| 状态 | 颜色 |
|------|------|
| due_at < 24h | 🔴 红 |
| due_at < 7d | 🟡 黄 |
| due_at > 7d 或无 | 🟢 绿 |
| fulfilled | ✅ 灰 |
| broken | ❌ 深红 |

---

## 7. 共享组件

### 7.1 topbar.html

```html
<header class="topbar">
  <a href="/" class="logo">🧠 memos-graph</a>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/state/nako">State</a>
    <a href="/timeline/nako">Timeline</a>
    <a href="/promises/nako">Promises</a>
  </nav>
  <div class="actions">
    <a href="/api/v1/health" title="Health">💚</a>
    <a href="/docs" title="API docs">📖</a>
  </div>
</header>
```

### 7.2 styles.css（核心变量）

```css
:root {
  --bg: #ffffff;
  --fg: #1a1a1a;
  --accent: #3b82f6;
  --danger: #ef4444;
  --warning: #f59e0b;
  --success: #10b981;
  --border: #e5e7eb;
  --shadow: 0 1px 3px rgba(0,0,0,0.1);
}

[data-theme="dark"] {
  --bg: #0f172a;
  --fg: #f1f5f9;
  --accent: #60a5fa;
  --border: #334155;
}

body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.card { background: var(--bg); border: 1px solid var(--border); padding: 1rem; border-radius: 8px; }
```

### 7.3 app.js（共用工具）

```js
// app.js
const API = '';  // 同源
async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function relativeTime(iso) {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return `${Math.floor(d)}s ago`;
  if (d < 3600) return `${Math.floor(d/60)}m ago`;
  if (d < 86400) return `${Math.floor(d/3600)}h ago`;
  return `${Math.floor(d/86400)}d ago`;
}
```

---

## 8. 静态资源

| 文件 | 大小 | 说明 |
|------|------|------|
| `static/styles.css` | ~5KB | CSS 变量 + 4 页面 |
| `static/app.js` | ~3KB | API helper + 相对时间 |
| `static/charts.js` | ~2KB | 折线图 (SVG path) |
| **合计** | **< 15KB** | 远低于 SPEC 200KB 预算 |

**不引**：
- chart.js / d3.js
- bootstrap / tailwind
- jQuery

---

## 9. 启动方式

```bash
memos-graph viewer --port 8080 --bind 127.0.0.1
# 或与 daemon 同进程
memos-graph serve --port 8765 --with-viewer 8080
```

**v0.1 必须是独立进程**（避免一个崩了两个都崩）。

---

## 10. 安全

> **⚠️ MOA v0.1.0 评审：原 §10 安全仅一句 `|e` 提及，不够具体**

### 10.1 XSS 防御（**强制**）

| 规则 | 实现 |
|------|------|
| **所有用户内容 escape** | `{{ content \| escape }}`（不用 `\|safe`）|
| **JSON 放到 `<script type="application/json">` 块** | 不放 HTML attribute（**MOA 评审：tojson 属性可能截断**）|
| **禁止 `\|safe` filter** | 除非显式 review 过 |
| **模板白名单** | 只允许 `\|e` `\|escape` `\|tojson` `\|length` `\|join` `\|upper` `\|lower` |
| **CSP 头** | `default-src 'self'; script-src 'self' 'unsafe-inline'`（不引 CDN）|
| **URL 参数验证** | `agent_id` 只能 `[a-z0-9-]+`（防 path traversal）|

### 10.2 数据流权限

| 端点 | viewer 允许 |
|------|----------|
| `GET /api/v1/agents/{id}/state` | ✅ |
| `PUT /api/v1/agents/{id}/state` | ❌（viewer 不能改 state）|
| `POST /api/v1/agents/{id}/heartbeat` | ✅（手动触发 OK）|
| `GET /api/v1/memories/...` | ✅ |
| `POST/PUT/DELETE /api/v1/memories/...` | ❌（viewer 只读）|
| `GET /api/v1/packs` | ✅ |
| `POST /api/v1/packs/install` | ❌（viewer 不能装 pack）|
| `POST /api/v1/promises` | ✅（允许 UI 创建）|
| `PUT /api/v1/promises/{id}` | ✅（标记 fulfilled/broken）|

**实现**：viewer 路由**只调白名单内的 endpoint**，不开放 viewer 调用所有 `/api/v1/*`。

### 10.3 其他

- **绑定 127.0.0.1**（**禁止 0.0.0.0**）
- **无登录**（localhost only）
- **CSRF**：viewer 不写 state → 无 CSRF 风险（POST 只触发 heartbeat）

---

## 11. 验收

- [ ] 4 个页面（Dashboard / State / Timeline / Promises）200 OK
- [ ] 模板渲染时**无 XSS 漏洞**（用户内容 escape）
- [ ] 静态资源 MIME 正确
- [ ] dark mode 切换正常
- [ ] 在 1024×768 分辨率下布局正常
- [ ] 在 1920×1080 下布局正常
- [ ] **总资源大小 < 200KB**
- [ ] 4 页面首屏 < 500ms（localhost）

---

**状态**：✅ Viewer Design v0.1 钉死，等待 MOA 评审 → 进入 Final Review
