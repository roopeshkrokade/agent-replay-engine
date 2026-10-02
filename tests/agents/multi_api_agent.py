"""
Test agent touching every API the replay gateway serves. Prints one RESULT line per call so a
recording and its replay can be compared line by line.

Endpoints come from OPENAI_BASE_URL / ANTHROPIC_BASE_URL, as for any agent under replay.
"""
import os
import threading

import agent_replay

agent_replay.autolog()

import anthropic  # noqa: E402 - instrumentation is enabled first
import openai  # noqa: E402

WEATHER_TOOL = {
    "name": "get_weather",
    "description": "Get the weather for a city.",
    "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
}


def result(name: str, value) -> None:
    print(f"RESULT {name}: {value}", flush=True)


def main():
    client = openai.OpenAI(max_retries=0)
    claude = anthropic.Anthropic(max_retries=0)

    with agent_replay.start_run(agent_id="multi_api_agent", agent_name="Multi-API Agent"):
        # 1. Streamed chat completion: recorded from the stream, replayed as a stream
        stream = client.chat.completions.create(
            model="fake-model", stream=True,
            # MULTI_API_VARIANT changes this prompt, to exercise divergence reporting
            messages=[{"role": "user", "content": "stream a haiku" + os.environ.get("MULTI_API_VARIANT", "")}])
        result("chat_stream", "".join(c.choices[0].delta.content or "" for c in stream if c.choices))

        # 2. OpenAI Responses API
        response = client.responses.create(model="fake-model", input="summarise the weather")
        result("responses", response.output_text)

        # 3. Embeddings (the SDK asks for base64 by default)
        embedding = client.embeddings.create(model="fake-embed", input=["tokyo", "osaka"])
        result("embeddings", [round(v, 3) for v in embedding.data[1].embedding])

        # 4. Anthropic tool round trip
        messages = [{"role": "user", "content": "weather in Tokyo?"}]
        first = claude.messages.create(model="fake-claude", max_tokens=100, messages=messages, tools=[WEATHER_TOOL])
        tool_use = next(b for b in first.content if b.type == "tool_use")
        result("anthropic_tool", f"{tool_use.name}({tool_use.input})")
        messages += [
            {"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in first.content]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": "75F"}]},
        ]
        final = claude.messages.create(model="fake-claude", max_tokens=100, messages=messages, tools=[WEATHER_TOOL])
        result("anthropic_final", final.content[0].text)

        # 5. A failing call the agent handles
        try:
            client.chat.completions.create(model="rate-limited", messages=[{"role": "user", "content": "hi"}])
            result("error", "no error")
        except openai.RateLimitError as exc:
            result("error", f"{type(exc).__name__} {exc.status_code}")

        # 6. Concurrent calls whose arrival order is not deterministic
        answers = {}

        def ask(prompt):
            reply = client.chat.completions.create(model="fake-model", messages=[{"role": "user", "content": prompt}])
            answers[prompt] = reply.choices[0].message.content

        threads = [threading.Thread(target=ask, args=(p,)) for p in ("parallel A", "parallel B", "parallel C")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        result("parallel", sorted(answers.items()))


if __name__ == "__main__":
    main()
