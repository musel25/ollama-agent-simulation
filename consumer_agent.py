import ollama
import httpx

PROVIDER_BASE_URL = "http://localhost:8001"

CONSUMER_SYSTEM_PROMPT = """You are a bandwidth procurement agent. Help the user acquire
network bandwidth packages from a provider. The provider offers three tiered packages:
Small (50 Mbps), Medium (100 Mbps), and Large (500 Mbps) — each valid for 10 minutes.
Use query_provider to check available tiers and their prices.
Use purchase_from_provider to buy a tier by specifying the exact tier name and its listed price.
Always show the token returned after a successful purchase."""

inter_agent_log: list[dict] = []
_active_model: str = "qwen3:4b"


def query_provider(question: str) -> str:
    """Query the provider for available bandwidth packages and their prices.

    Args:
        question: The question about available bandwidth packages or inventory.
    """
    inter_agent_log.append({"from": "consumer", "message": f"GET /catalog — {question}"})

    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/catalog")
        resp.raise_for_status()
        catalog: list[dict] = resp.json()

    inter_agent_log.append({
        "from": "provider_step",
        "role": "tool_call",
        "content": f"GET /catalog → {len(catalog)} tiers",
    })

    lines = [
        f"{t['tier']}: {t['mbps']} Mbps / {t['duration_min']} min / {t['price_eth']} ETH "
        f"({t['slots']} slots available)"
        for t in catalog
    ]
    result = "\n".join(lines)

    inter_agent_log.append({"from": "provider_step", "role": "tool_result", "content": result})
    inter_agent_log.append({"from": "provider", "message": result})
    return result


def purchase_from_provider(tier: str, agreed_price: float) -> str:
    """Purchase a bandwidth tier from the provider.

    Args:
        tier: The tier name to purchase — one of: small, medium, large.
        agreed_price: The price in ETH exactly as listed in the catalog.
    """
    payload = {"tier": tier, "agreed_price": agreed_price}
    inter_agent_log.append({
        "from": "consumer",
        "message": f"POST /confirm {payload}",
    })
    inter_agent_log.append({
        "from": "provider_step",
        "role": "tool_call",
        "content": f"POST /confirm(tier={tier!r}, agreed_price={agreed_price})",
    })

    with httpx.Client() as client:
        resp = client.post(f"{PROVIDER_BASE_URL}/confirm", json=payload)

    if resp.status_code != 200:
        detail = resp.json().get("detail", resp.text)
        result = f"ERROR: {detail}"
        inter_agent_log.append({"from": "provider_step", "role": "tool_result", "content": result})
        inter_agent_log.append({"from": "provider", "message": result})
        return result

    data = resp.json()
    token = data["token_id"]
    result = (
        f"SUCCESS — token: {token} | tier: {data['tier']} | "
        f"{data['mbps']} Mbps for {data['duration_min']} min"
    )
    inter_agent_log.append({"from": "provider_step", "role": "tool_result", "content": result})
    inter_agent_log.append({"from": "provider", "message": result})
    return result


def run_consumer(user_message: str, model: str = "qwen3:4b") -> tuple[str, list[dict]]:
    global _active_model
    _active_model = model

    messages = [
        {"role": "system", "content": CONSUMER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools = [query_provider, purchase_from_provider]

    while True:
        response = ollama.chat(model=model, messages=messages, tools=tools)
        msg = response.message

        if not msg.tool_calls:
            break

        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = tc.function.arguments or {}

            if tool_name == "query_provider":
                result = query_provider(**args)
            elif tool_name == "purchase_from_provider":
                result = purchase_from_provider(**args)
            else:
                result = f"ERROR: unknown tool {tool_name}"

            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": str(result),
            })

    final_text = msg.content or ""
    return final_text, list(inter_agent_log)


def get_inter_agent_log() -> list[dict]:
    return inter_agent_log


def clear_inter_agent_log() -> None:
    global inter_agent_log
    inter_agent_log = []
