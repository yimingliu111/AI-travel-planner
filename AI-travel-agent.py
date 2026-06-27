"""
AI-travel-agent.py - AI 旅行规划师 Web 版（多用户自带 API Key）
运行: python AI-travel-agent.py
"""

import json, sys, os, gradio as gr

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from FirstAgentTest import (
    get_weather, search_web, calculate,
    SYSTEM_PROMPT, TOOLS, MAX_HISTORY, MAX_TOOL_ROUNDS,
)
from user_manager import login, register, update_user, get_api_keys, save_api_keys
from openai import OpenAI

sessions = {}


def run_travel_agent(message, history, username, api_keys):
    if not api_keys.get("llm_api_key"):
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant",
                        "content": "请先在左侧填写 DeepSeek 和 Tavily 的 API 密钥。"})
        yield history, "未配置 API 密钥"
        return

    session = sessions.setdefault(username, {"history": []})
    chat_hist = session["history"]

    llm_key = api_keys["llm_api_key"]
    llm_url = api_keys.get("llm_base_url", "https://api.deepseek.com")
    model_id = api_keys.get("model_id", "deepseek-v4-flash")
    tavily_key = api_keys.get("tavily_api_key", "")

    llm = OpenAI(api_key=llm_key, base_url=llm_url)

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs += chat_hist[-MAX_HISTORY:]
    msgs.append({"role": "user", "content": message})
    chat_hist.append({"role": "user", "content": message})

    tool_log = []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = llm.chat.completions.create(
                model=model_id, messages=msgs, tools=TOOLS,
                tool_choice="auto", max_tokens=1024, temperature=0.7)
        except Exception as e:
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": f"API 错误: {e}"})
            yield history, f"API 错误: {e}"
            return

        msg = resp.choices[0].message
        if not msg.tool_calls:
            break

        msgs.append(msg)
        chat_hist.append({"role": "assistant", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            name = tc.function.name
            if name == "get_weather":
                result = get_weather(args["city"])
                tool_log.append(f"[天气] {args['city']}")
            elif name == "search_web":
                result = search_web(args["query"], tavily_key)
                tool_log.append(f"[搜索] {args['query']}")
            elif name == "calculate":
                result = calculate(args["expression"])
                tool_log.append(f"[计算] {args['expression']}")
            else:
                result = {"error": f"未知工具: {name}"}
            tm = {"role": "tool", "tool_call_id": tc.id,
                  "content": json.dumps(result, ensure_ascii=False)}
            msgs.append(tm)
            chat_hist.append(tm)

    # 流式生成
    try:
        stream_resp = llm.chat.completions.create(
            model=model_id, messages=msgs, max_tokens=1024,
            temperature=0.7, stream=True)
        answer = ""
        for chunk in stream_resp:
            if chunk.choices[0].delta.content:
                answer += chunk.choices[0].delta.content
    except Exception as e:
        answer = f"生成错误: {e}"

    chat_hist.append({"role": "assistant", "content": answer})
    update_user(username, "history", chat_hist)

    prefix = ""
    if tool_log:
        prefix = "**工具调用:**\n" + "\n".join(f"- {t}" for t in tool_log) + "\n\n---\n"
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": prefix + answer})
    status = f"[{username}] {len(chat_hist)//2}轮对话 | {len(tool_log)}次工具"
    yield history, status


# ---- 用户操作 ----

def register_user(username, password):
    if not username or not password:
        return "请输入用户名和密码。"
    if register(username, password):
        return f"注册成功！请登录: {username}"
    return f"用户名 '{username}' 已被占用。"


def login_user(username, password, auth_state):
    if not username or not password:
        return auth_state, "请输入用户名和密码。"
    data = login(username, password)
    if data:
        n = len(data.get("history", [])) // 2
        keys = get_api_keys(username, password) or {}
        auth_state["logged_in"] = True
        auth_state["username"] = username
        auth_state["user_data"] = data
        auth_state["api_keys"] = keys
        auth_state["password"] = password
        msg = f"欢迎回来，{username}！（历史记录 {n} 轮）"
        if not keys.get("llm_api_key"):
            msg += "\n\n请在下方填入 API 密钥，然后点击「保存密钥」。"
        return auth_state, msg
    return auth_state, "登录失败，用户名或密码错误。"


def save_keys(username, password, llm_key, llm_url, model_id, tavily_key, auth_state):
    if not login(username, password):
        return auth_state, "验证失败，请先登录。"
    save_api_keys(username, password, llm_key, llm_url, tavily_key, model_id)
    keys = get_api_keys(username, password) or {}
    auth_state["api_keys"] = keys
    return auth_state, "API 密钥已加密保存！"


# ---- 界面 ----

css = ".gradio-container { max-width: 1000px !important; } footer { display: none !important; }"

with gr.Blocks(title="AI 旅行规划师") as demo:
    gr.Markdown("# AI 旅行规划师\n输入目的地，自动查天气、搜攻略、算预算")

    auth_state = gr.State({"logged_in": False, "username": "", "user_data": {}, "api_keys": {}})

    with gr.Row():
        with gr.Column(scale=2, min_width=260):
            gr.Markdown("### 账户")
            u = gr.Textbox(label="用户名", placeholder="请输入用户名")
            p = gr.Textbox(label="密码", placeholder="请输入密码", type="password")

            with gr.Accordion("API 密钥", open=True):
                llm_key = gr.Textbox(label="DeepSeek API Key", placeholder="sk-...", type="password")
                llm_url = gr.Textbox(label="Base URL", value="https://api.deepseek.com")
                model_id = gr.Textbox(label="模型名称", value="deepseek-v4-flash")
                tavily_key = gr.Textbox(label="Tavily API Key", placeholder="tvly-...", type="password")

            with gr.Row():
                login_btn = gr.Button("登录", variant="primary")
                reg_btn = gr.Button("注册")
                save_btn = gr.Button("保存密钥", size="sm")
            auth_msg = gr.Markdown("")

        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话", height=520)
            msg = gr.Textbox(label="目的地",
                             placeholder="例如：我想去成都玩3天，两个人，预算5000")
            status = gr.Markdown("请先登录，配置 API 密钥，然后输入目的地。")

    # 事件
    login_btn.click(login_user, [u, p, auth_state], [auth_state, auth_msg])
    reg_btn.click(register_user, [u, p], [auth_msg])
    save_btn.click(save_keys, [u, p, llm_key, llm_url, model_id, tavily_key, auth_state],
                   [auth_state, auth_msg])

    def auth_check(message, history, username, password, auth_state):
        if not auth_state.get("logged_in"):
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": "请先点击「登录」按钮。"})
            yield history, "未登录"
            return
        keys = auth_state.get("api_keys", {})
        if not keys.get("llm_api_key"):
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant",
                            "content": "请先在左侧填写 API 密钥，然后点击「保存密钥」。"})
            yield history, "未配置 API 密钥"
            return
        for h, s in run_travel_agent(message, history, username, keys):
            yield h, s

    msg.submit(auth_check, [msg, chatbot, u, p, auth_state], [chatbot, status])\
       .then(lambda: "", None, [msg])


if __name__ == "__main__":
    print("=" * 50)
    print("  AI 旅行规划师")
    print("=" * 50)
    demo.launch(server_name="127.0.0.1", share=False, theme=gr.themes.Soft(), css=css)
