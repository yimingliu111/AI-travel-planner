"""
FirstAgentTest.py - AI 旅行规划师核心模块（多用户自带 API Key）
"""

import os, sys, json, math, time, logging, requests
from openai import OpenAI
from tavily import TavilyClient

_HERE = os.path.dirname(os.path.realpath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from user_manager import login, register, update_user, get_api_keys

# ============================================================
# --- 日志 ---
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_HERE, "agent.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# --- 工具函数（不依赖 API key） ---
# ============================================================
def get_weather(city: str) -> dict:
    logger.info(f"get_weather: city={city}")
    try:
        r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        if r.status_code == 200:
            d = r.json()
            c = d["current_condition"][0]
            return {"city": city, "temperature": f"{c['temp_C']}°C",
                    "weather": c["weatherDesc"][0]["value"],
                    "humidity": f"{c['humidity']}%",
                    "wind_speed": f"{c['windspeedKmph']} km/h"}
        return {"error": f"Weather API status: {r.status_code}"}
    except Exception as e:
        return {"error": f"Weather error: {str(e)}"}


def search_web(query: str, tavily_key: str = "") -> list:
    logger.info(f"search_web: query={query}")
    try:
        client = TavilyClient(api_key=tavily_key)
        result = client.search(query, search_depth="basic")
        return result.get("results", [])[:5]
    except Exception as e:
        return [{"error": f"Search error: {str(e)}"}]


def calculate(expression: str) -> dict:
    logger.info(f"calculate: {expression}")
    safe_dict = {"abs": abs, "round": round, "min": min, "max": max,
                 "sum": sum, "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
                 "cos": math.cos, "log": math.log, "pi": math.pi, "e": math.e}
    try:
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": f"Calc error: {str(e)}"}


# ============================================================
# --- System Prompt & Tools ---
# ============================================================
SYSTEM_PROMPT = """你是一个专业的 AI 旅行规划师。当用户提出任何旅行目的地时：

【流程】
1. get_weather 查询目的地天气
2. search_web 搜索该地的酒店、门票、交通、餐饮人均费用
3. calculate 根据搜索结果估算总费用

【输出格式】
- 天气：[摘要]
- 住宿：[费用明细]
- 门票：[费用明细]
- 餐饮：[费用明细]
- 交通：[费用明细]
- 总预算：[汇总]

用中文回复，数据有依据。"""

TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "查询指定城市的实时天气",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string", "description": "城市名"}},
                       "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "搜索旅游攻略、酒店价格、门票",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "计算数学表达式",
        "parameters": {"type": "object",
                       "properties": {"expression": {"type": "string", "description": "表达式"}},
                       "required": ["expression"]}}},
]

MAX_HISTORY = 20
MAX_TOOL_ROUNDS = 5


# ============================================================
# --- Agent 核心（参数化 API key） ---
# ============================================================
def run_agent(user_input: str, username: str,
              llm_key: str, llm_url: str, model_id: str, tavily_key: str) -> str:
    """用指定用户的 API key 运行 Agent"""

    # 从 users.json 读取用户历史
    user_data = login(username, "")  # 特殊：只取数据不验证密码
    # 上面 login 会因为密码不对返回 None，我们改用 load_users
    from user_manager import load_users
    all_users = load_users()
    user_data = all_users.get(username, {})
    history = user_data.get("history", [])

    # 创建该用户专属的 LLM 客户端
    llm = OpenAI(api_key=llm_key, base_url=llm_url)
    os.environ['TAVILY_API_KEY'] = tavily_key  # tavily 读环境变量

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs += history[-MAX_HISTORY:]
    msgs.append({"role": "user", "content": user_input})
    history.append({"role": "user", "content": user_input})

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = llm.chat.completions.create(
                model=model_id, messages=msgs, tools=TOOLS,
                tool_choice="auto", max_tokens=1024, temperature=0.7)
        except Exception as e:
            return f"LLM Error: {e}"

        msg = resp.choices[0].message
        if not msg.tool_calls:
            break

        msgs.append(msg)
        history.append({"role": "assistant", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            name = tc.function.name
            if name == "get_weather":
                result = get_weather(args["city"])
            elif name == "search_web":
                result = search_web(args["query"], tavily_key)
            elif name == "calculate":
                result = calculate(args["expression"])
            else:
                result = {"error": f"Unknown: {name}"}
            tm = {"role": "tool", "tool_call_id": tc.id,
                  "content": json.dumps(result, ensure_ascii=False)}
            msgs.append(tm)
            history.append(tm)

    # 生成最终回答
    try:
        resp = llm.chat.completions.create(
            model=model_id, messages=msgs, max_tokens=1024, temperature=0.7)
        answer = resp.choices[0].message.content or ""
    except Exception as e:
        answer = f"Generation Error: {e}"

    history.append({"role": "assistant", "content": answer})
    update_user(username, "history", history)
    return answer


# ============================================================
# --- 命令行入口（需要用户自己填 API key） ---
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  AI Travel Planner - BYOK Mode")
    print("=" * 50)

    u = input("Username: ").strip()
    p = input("Password: ").strip()
    if not login(u, p):
        print("Login failed.")
        sys.exit()

    keys = get_api_keys(u)
    if not keys or not keys.get("llm_api_key"):
        print("\nFirst time? Enter your API keys:")
        keys = {
            "llm_api_key": input("DeepSeek API Key: ").strip(),
            "llm_base_url": input("Base URL [https://api.deepseek.com]: ").strip() or "https://api.deepseek.com",
            "model_id": input("Model [deepseek-v4-flash]: ").strip() or "deepseek-v4-flash",
            "tavily_api_key": input("Tavily API Key: ").strip(),
        }
        from user_manager import update_api_keys
        update_api_keys(u, **keys)

    print(f"\nWelcome {u}! Type 'quit' to exit.\n")

    while True:
        inp = input(f"You [{u}]: ").strip()
        if inp.lower() in ("quit", "exit", "q"):
            break
        if not inp:
            continue
        ans = run_agent(inp, u, keys["llm_api_key"], keys["llm_base_url"],
                        keys["model_id"], keys["tavily_api_key"])
        print(f"\nAssistant:\n{ans}\n")
