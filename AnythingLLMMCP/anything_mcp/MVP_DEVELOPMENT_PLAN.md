# AnythingLLM MCP Server MVP 寮€鍙戣鍒?
## 1. 椤圭洰姒傝堪

鏋勫缓涓€涓熀浜?MCP 2026-07-28 鍗忚鐨?Python MCP Server锛屼綔涓?AnythingLLM 鐨勬ˉ鎺ュ眰锛屾彁渚?AI 闂瓟鑳藉姏銆?
**鐩爣**: 鎻愪緵涓€涓?MCP Tool锛屼娇 AI 搴旂敤鑳介€氳繃宸ヤ綔鍖轰腑鐨勬枃妗ｇ煡璇嗚繘琛岄棶绛斻€?
---

## 2. 鎶€鏈爤

| 缁勪欢 | 閫夊瀷 | 璇存槑 |
|------|------|------|
| MCP 鍗忚鐗堟湰 | 2026-07-28 | Stateless core, JSON-RPC 2.0 |
| Python SDK | `mcp>=2.0` | 瀹樻柟 Python SDK v2 |
| 浼犺緭灞?| Streamable HTTP | `mcp.run --transport streamable-http` |
| HTTP 瀹㈡埛绔?| `httpx` | 寮傛璇锋眰 AnythingLLM API |
| AnythingLLM 鍦板潃 | `http://localhost:3001` | 鏈満瀹炰緥 |
| API Key | `your-anythingllm-api-key` | Bearer token |

---

## 3. AnythingLLM API 鍒嗘瀽锛堝叧閿鐐癸級

| 绔偣 | 鏂规硶 | 鐢ㄩ€?| 璁″垝浣跨敤 |
|------|------|------|----------|
| `/api/v1/workspaces` | GET | 鍒楀嚭鎵€鏈夊伐浣滃尯 | 鉁?鍚姩鏃惰幏鍙栧伐浣滃尯鍒楄〃 |
| `/api/v1/workspace/:slug` | GET | 鑾峰彇宸ヤ綔鍖鸿鎯?| 鉁?楠岃瘉宸ヤ綔鍖哄瓨鍦ㄦ€?|
| `/api/v1/workspace/:slug/chat` | POST | 鍚屾鑱婂ぉ锛堝惈鏂囨。涓婁笅鏂囷級 | 鉁?**鏍稿績鍔熻兘绔偣** |
| `/api/v1/workspace/:slug/stream-chat` | POST | 娴佸紡鑱婂ぉ | 鉂?MVP 鏆備笉闇€瑕?|
| `/api/v1/workspace/:slug/vector-search` | POST | 绾悜閲忔绱?| 鉂?MVP 鐢?chat 绔偣鏇夸唬 |

### 璁よ瘉鏂瑰紡
```
Authorization: Bearer your-anythingllm-api-key
Content-Type: application/json
```

### `/api/v1/workspace/:slug/chat` 璇锋眰浣?```json
{
  "prompt": "鐢ㄦ埛闂鏂囨湰",
  "threadId": "鍙€夌殑绾跨▼ID",
  "searchTopK": 5,
  "searchScoreThreshold": 0.2
}
```

---

## 4. MCP Server 璁捐

### 4.1 鏋舵瀯鍥?
```
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?    MCP 2026-07-28      鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? MCP Client  鈹傗梽鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈻衡攤  mcp-anythingllm  鈹?鈹? (Claude绛?  鈹?  Streamable HTTP       鈹?    Server        鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?   http://localhost:8000/          鈹?                                                     鈹?httpx
                                                     鈻?                                            鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                                            鈹?AnythingLLM API   鈹?                                            鈹?localhost:3001    鈹?                                            鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

### 4.2 鍞竴 Tool: `workspace_chat`

**鍚嶇О**: `workspace_chat`

**鎻忚堪**: 浠庢寚瀹氱殑 AnythingLLM 宸ヤ綔鍖轰腑鎻愬彇鏂囨。淇℃伅杩涜 AI 闂瓟

**杈撳叆鍙傛暟** (JSON Schema):
```json
{
  "type": "object",
  "properties": {
    "workspace_slug": {
      "type": "string",
      "description": "AnythingLLM 宸ヤ綔鍖虹殑 slug 鏍囪瘑绗?
    },
    "question": {
      "type": "string",
      "description": "瑕佹彁鍑虹殑闂锛屽皢鍩轰簬宸ヤ綔鍖烘枃妗ｇ煡璇嗗洖绛?
    },
    "search_top_k": {
      "type": "integer",
      "description": "妫€绱㈢殑鏂囨。鐗囨鏁伴噺",
      "default": 5,
      "minimum": 1,
      "maximum": 20
    },
    "search_threshold": {
      "type": "number",
      "description": "妫€绱㈢浉浼煎害闃堝€?,
      "default": 0.2,
      "minimum": 0.0,
      "maximum": 1.0
    }
  },
  "required": ["workspace_slug", "question"]
}
```

**杩斿洖鍊?*: AnythingLLM 杩斿洖鐨勫畬鏁?AI 鍥炵瓟鏂囨湰

**鍐呴儴娴佺▼**:
1. 鏍￠獙 `workspace_slug` 鏄惁瀛樺湪锛堣皟鐢?`GET /v1/workspaces`锛?2. 璋冪敤 `POST /v1/workspace/{slug}/chat` 鍙戦€侀棶棰樺拰妫€绱㈠弬鏁?3. 杩斿洖 AI 鍥炵瓟鍐呭

---

## 5. 椤圭洰缁撴瀯

```
D:\anything\
鈹溾攢鈹€ pyproject.toml          # 渚濊禆澹版槑
鈹溾攢鈹€ .env                    # 鐜鍙橀噺 (API_KEY, ANYTHINGLLM_URL)
鈹溾攢鈹€ src/
鈹?  鈹斺攢鈹€ mcp_anythingllm/
鈹?      鈹溾攢鈹€ __init__.py
鈹?      鈹溾攢鈹€ server.py       # MCP Server 涓诲叆鍙?鈹?      鈹溾攢鈹€ anythingllm.py  # AnythingLLM API 瀹㈡埛绔?鈹?      鈹斺攢鈹€ config.py       # 閰嶇疆绠＄悊
鈹斺攢鈹€ MVP_DEVELOPMENT_PLAN.md # 鏈枃浠?```

---

## 6. 鍒嗛樁娈靛疄鏂借鍒?
### Phase 1: 鐜鎼缓 (棰勮 1 灏忔椂)

**浠诲姟**:
- [ ] 鍒涘缓 Python 椤圭洰锛宍pip install "mcp[cli]" httpx python-dotenv`
- [ ] 纭 Python 3.10+ 鐜
- [ ] 纭鏈湴 AnythingLLM 瀹炰緥鍙闂?(`http://localhost:3001/api/docs`)
- [ ] 鍒涘缓椤圭洰楠ㄦ灦鏂囦欢

**浜у嚭**: 鍙繍琛岀殑绌虹櫧椤圭洰楠ㄦ灦锛屼緷璧栧凡瀹夎

**楠岃瘉**: `python -c "import mcp; print(mcp.__version__)"` 杈撳嚭 >= 2.0

---

### Phase 2: AnythingLLM 瀹㈡埛绔疄鐜?(棰勮 2 灏忔椂)

**浠诲姟**:
- [ ] 鍒涘缓 `src/mcp_anythingllm/config.py` 鈥?璇诲彇鐜鍙橀噺
- [ ] 鍒涘缓 `src/mcp_anythingllm/anythingllm.py` 鈥?瀹炵幇:
  - `list_workspaces()` 鈥?鑾峰彇鎵€鏈夊伐浣滃尯鍒楄〃
  - `get_workspace(slug)` 鈥?楠岃瘉宸ヤ綔鍖烘槸鍚﹀瓨鍦?  - `chat(slug, question, top_k, threshold)` 鈥?璋冪敤 chat 绔偣
- [ ] 瀹炵幇缁熶竴鐨勯敊璇鐞嗭紙API 寮傚父銆佽秴鏃躲€佽璇佸け璐ワ級

**鍏抽敭瀹炵幇瑕佺偣**:
```python
# 缁熶竴璇锋眰澶?headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# chat 璋冪敤绀轰緥
async def chat(slug, question, search_top_k=5, search_threshold=0.2):
    url = f"{BASE_URL}/api/v1/workspace/{slug}/chat"
    payload = {
        "prompt": question,
        "searchTopK": search_top_k,
        "searchScoreThreshold": search_threshold
    }
    response = await httpx.post(url, json=payload, headers=headers)
    return response.json()
```

**浜у嚭**: 鐙珛鍙敤鐨?AnythingLLM API 瀹㈡埛绔ā鍧?
**楠岃瘉**: 缂栧啓娴嬭瘯鑴氭湰鐩存帴璋冪敤锛岄獙璇佽繑鍥炴暟鎹粨鏋?
---

### Phase 3: MCP Server 瀹炵幇 (棰勮 2 灏忔椂)

**浠诲姟**:
- [ ] 鍒涘缓 `src/mcp_anythingllm/server.py`
- [ ] 浣跨敤 `mcp.server.MCPServer` 鍒濆鍖?Server
- [ ] 鐢?`@mcp.tool()` 瑁呴グ鍣ㄦ敞鍐?`workspace_chat`
- [ ] 閰嶇疆 Streamable HTTP 浼犺緭锛岀鍙?8000
- [ ] 鍦?`_meta` 涓惡甯﹀崗璁増鏈拰瀹㈡埛绔俊鎭?
**鍏抽敭瀹炵幇瑕佺偣**:
```python
from mcp.server import MCPServer

mcp = MCPServer("anythingllm-mcp")

@mcp.tool()
async def workspace_chat(
    workspace_slug: str,
    question: str,
    search_top_k: int = 5,
    search_threshold: float = 0.2
) -> str:
    """浠庢寚瀹氬伐浣滃尯鎻愬彇鏂囨。淇℃伅杩涜AI闂瓟"""
    client = AnythingLLMClient()
    result = await client.chat(workspace_slug, question, search_top_k, search_threshold)
    return result["answer"]  # 鎴栫被浼煎瓧娈?```

**浜у嚭**: 瀹屾暣鐨?MCP Server 鍙惎鍔ㄨ繍琛?
**楠岃瘉**: `mcp dev src/mcp_anythingllm/server.py` 鑳芥甯稿惎鍔ㄥ苟閫氳繃 Inspector 璋冪敤

---

### Phase 4: 闆嗘垚娴嬭瘯 (棰勮 1 灏忔椂)

**浠诲姟**:
- [ ] 鍚姩 MCP Server (`mcp run --transport streamable-http`)
- [ ] 閫氳繃 MCP Inspector 璋冪敤 `workspace_chat`
- [ ] 娴嬭瘯杈圭晫鎯呭喌锛氫笉瀛樺湪鐨勫伐浣滃尯銆佽秴闀块棶棰樸€佺┖闂
- [ ] 楠岃瘉杩斿洖鍐呭涓?AnythingLLM UI 涓殑鍥炵瓟涓€鑷?
**娴嬭瘯鐢ㄤ緥**:
| 鐢ㄤ緥 | 杈撳叆 | 鏈熸湜 |
|------|------|------|
| 姝ｅ父闂瓟 | 鏈夋晥 slug + 鍚堢悊闂 | 杩斿洖 AI 鍥炵瓟 |
| 鏈煡宸ヤ綔鍖?| 涓嶅瓨鍦ㄧ殑 slug | 杩斿洖鏄庣‘鐨勯敊璇俊鎭?|
| 缂虹渷鍙傛暟 | 鍙彁渚?slug 鍜?question | 浣跨敤榛樿妫€绱㈠弬鏁?|

**浜у嚭**: 娴嬭瘯閫氳繃鐨?MVP 鍙繍琛岀郴缁?
---

## 7. 鍏抽敭閰嶇疆

### 鐜鍙橀噺 (`.env`)
```env
ANYTHINGLLM_BASE_URL=http://localhost:3001
ANYTHINGLLM_API_KEY=your-anythingllm-api-key
MCP_HOST=0.0.0.0
MCP_PORT=8000
```

### `pyproject.toml` 渚濊禆
```toml
[project]
name = "mcp-anythingllm"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=2.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
]
```

---

## 8. 鍗忚鍏煎鎬ф敞鎰忎簨椤?
MCP 2026-07-28 鐨勯噸瑕佸彉鍖栵紙Python SDK v2 鑷姩澶勭悊锛屼絾闇€浜嗚В锛夛細

1. **鏃犵姸鎬?*: 姣忎釜璇锋眰鎼哄甫 `_meta`锛屾棤闇€ `initialize` 鎻℃墜 鈥?Python SDK v2 鑷姩澶勭悊
2. **Streamable HTTP**: 浣跨敤 `POST /mcp` 绔偣锛宍Mcp-Method` 鍜?`Mcp-Name` 澶?3. **server/discover**: SDK 鑷姩鏀寔
4. **宸插純鐢?*: `initialize`/`initialized` 浜ゆ崲銆乣Mcp-Session-Id` header 鈥?涓嶈浣跨敤
5. **Python SDK v2** (`mcp>=2.0`) 宸插畬鍏ㄦ敮鎸?2026-07-28

---

## 9. MVP 鑼冨洿杈圭晫锛堟槑纭笉鍋氾級

- 鉂?涓嶆敮鎸佸宸ヤ綔鍖洪€夋嫨锛堝浐瀹氫竴涓伐浣滃尯锛?- 鉂?涓嶅疄鐜版祦寮忓洖绛旓紙SSE锛?- 鉂?涓嶅疄鐜版枃妗ｄ笂浼?绠＄悊鍔熻兘
- 鉂?涓嶅疄鐜扮嚎绋嬬鐞嗗姛鑳?- 鉂?涓嶅疄鐜板悜閲忔绱㈠崟鐙毚闇?- 鉂?涓嶅疄鐜扮敤鎴疯璇佺郴缁燂紙浠呬娇鐢ㄥ浐瀹?API Key锛?- 鉂?涓嶉儴缃插埌鐢熶骇鐜

---

## 10. 棰勪及鎬绘椂闂?
| 闃舵 | 棰勪及鏃堕棿 |
|------|----------|
| Phase 1: 鐜鎼缓 | 1 灏忔椂 |
| Phase 2: API 瀹㈡埛绔?| 2 灏忔椂 |
| Phase 3: MCP Server | 2 灏忔椂 |
| Phase 4: 闆嗘垚娴嬭瘯 | 1 灏忔椂 |
| **鎬昏** | **~6 灏忔椂** |

---

## 11. 鍚姩鍛戒护锛堝紑鍙戝畬鎴愬悗锛?
```bash
# 鍚姩 MCP Server (Streamable HTTP)
mcp run src/mcp_anythingllm/server.py --transport streamable-http --port 8000

# 鎴栦娇鐢?dev 妯″紡锛堝甫 Inspector锛?mcp dev src/mcp_anythingllm/server.py
```

---

## 12. 鍚庣画璺嚎鍥撅紙瓒呭嚭 MVP锛?
1. 澧炲姞 `list_workspaces` 鍜?`get_workspace` 宸ュ叿
2. 澧炲姞 `workspace_vector_search` 宸ュ叿
3. 鏀寔澶氫釜宸ヤ綔鍖洪厤缃?4. 澧炲姞娴佸紡鍥炵瓟鏀寔
5. 澧炲姞瀵硅瘽绾跨▼绠＄悊
6. 鏀寔 SSE 浼犺緭
7. 娣诲姞缂撳瓨鍜岄噸璇曟満鍒?