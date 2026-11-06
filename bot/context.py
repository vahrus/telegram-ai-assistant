"""Сборка сообщений для модели.

Оценка токенов здесь нужна только чтобы уложиться в окно контекста до запроса.
В статистику пользователя она не записывается: туда попадают поля usage ответа API.
"""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    if not text:
        return 1
    # Завышенная оценка для смешанного русского и английского текста.
    return max(1, len(text) // 2 + 1)


def build_context(
    *,
    mode_prompt: str,
    memories: list[str],
    history: list[dict[str, str]],
    user_message: str,
    max_history_messages: int,
    context_window: int,
    max_output_tokens: int,
) -> list[dict[str, str]]:
    system = [{"role": "system", "content": mode_prompt}]
    memory_messages: list[dict[str, str]] = []
    prepared_memories = [item.strip() for item in memories if item and item.strip()]
    if prepared_memories:
        facts = "\n".join(f"- {item}" for item in prepared_memories)
        memory_messages.append(
            {
                "role": "system",
                "content": (
                    "Долгосрочные факты, которые пользователь явно попросил запомнить. "
                    "Используй их, только если они уместны в ответе:\n"
                    f"{facts}"
                ),
            }
        )

    selected: list[dict[str, str]] = []
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue
        selected.append({"role": role, "content": content})
    if max_history_messages < 1:
        selected = []
    else:
        selected = selected[-max_history_messages:]

    fresh_user = {"role": "user", "content": user_message}
    budget = context_window - max_output_tokens
    if budget < 1:
        budget = 1

    def weight(messages: list[dict[str, str]]) -> int:
        return sum(estimate_tokens(message["content"]) + 4 for message in messages)

    fixed = system + memory_messages + [fresh_user]
    while selected and weight(fixed + selected) > budget:
        selected.pop(0)
    return system + memory_messages + selected + [fresh_user]
