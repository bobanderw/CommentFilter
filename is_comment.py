import os
import sys
import re
import json
import asyncio
from pathlib import Path

from openai import OpenAI
client = OpenAI(
    base_url='http://localhost:11434/v1/',
    api_key='ollama', #实际上本地模型不需要api_key
)

import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log(message, level="info"):
    if level == "debug":
        logging.debug(message)
    elif level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)
    elif level == "critical":
        logging.critical(message)

reg_int = re.compile(r"\d+")
reg_float = re.compile(r"\d+\.\d+")

P_SYS = """
Input text:
{text}

---

# Instruction: Please categorize the input text, ensuring that it can only belong to one category,
by determining whether it belongs to ad words, sublet words, tenant comments, or other.
And output an JSON Object following below schema.


# Schema:
class Output:
    belongs_to: int: 1 for ad words, 2 for sublet words, 3 for tenant comments, 4 for other
""".strip()

P_USER = """
The output of the classification result is:
```JSON
"""


def judge_comment(
        text: str
):

    # prompt
    role_msgs = [
        {
            "role": "system",
            "content": P_SYS.format(text=text),
        },
        {
            "role": "user",
            "content": P_USER.format(),
        },
    ]

    out = {}
    try:
        
        # 使用openai的原生流式输出生成结果
        responses = client.chat.completions.create(
            model="llama3",
            messages=role_msgs,
            timeout=100,
            max_tokens=256,
            response_format={"type": "json_object"},
            stream=True,
        )

        sentence = ""

        for chunk in responses:
            if not chunk:
                continue
            if chunk is None:
                break
            if chunk.choices[0].delta.content:
                sentence += chunk.choices[0].delta.content
                out = parse_custom_json(sentence)
                # print(out)
        if not out or not isinstance(out, dict) or "belongs_to" not in out:
            return None
        category = out.get("belongs_to")

        return category

    except asyncio.TimeoutError as ex:
        log.error(f"Timeout occurs during processing with LLM: {ex}")
        if out and isinstance(out, dict) and out.get("translated"):
            return out.get("translated")
        return None  


def parse_custom_json(text, default=None):
    if not text:
        return default

    try:
        text = text.strip().strip("```").strip("`").strip('"""').strip("'''").strip()
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
        return json.loads(text)
    except Exception as ex:
        pass

    data = None
    inside_string = False
    current_string = ""
    stack = []
    key = None
    value = ""
    inside_value = False
    i = 0

    while i < len(text):
        char = text[i]

        if char == '"' and (
                i == 0 or text[i - 1] != "\\"
        ):  # Check for unescaped quotes
            inside_value = False
            value = ""
            inside_string = not inside_string
            if not inside_string:
                # When closing a string, decide where to put it
                if stack:
                    if isinstance(stack[-1], dict):
                        if key is None:
                            key = current_string  # Set the key if none is set
                        else:
                            stack[-1][key] = current_string  # Set the value in the dict
                            key = None  # Reset key for next item
                    elif isinstance(stack[-1], list):
                        pass
                        # stack[-1].append(current_string)  # Add to list if inside a list
                current_string = ""
        elif inside_string:
            current_string += char  # Collect the string inside quotes

            if stack and isinstance(stack[-1], list):
                if stack[-1]:
                    stack[-1][-1] = current_string
                else:
                    stack[-1].append(current_string)
            elif stack and isinstance(stack[-1], dict) and key:
                stack[-1][key] = current_string

        elif char == "{":
            inside_value = False
            value = ""
            new_dict = {}

            if data is None:
                data = new_dict
            if stack:
                if isinstance(stack[-1], list):
                    stack[-1].append(new_dict)
                elif isinstance(stack[-1], dict) and key is not None:
                    stack[-1][key] = new_dict
                    key = None
            stack.append(new_dict)
        elif char == "[":
            inside_value = False
            value = ""
            new_list = []
            if data is None:
                data = new_list
            if stack:
                if isinstance(stack[-1], dict) and key is not None:
                    stack[-1][key] = new_list
                    key = None
            stack.append(new_list)
        elif char == "}":
            inside_value = False
            value = ""

            if stack and isinstance(stack[-1], dict):
                if not stack:
                    break
                stack.pop()

        elif char == "]":
            inside_value = False
            value = ""

            if stack and isinstance(stack[-1], list):
                if not stack:
                    break

                stack.pop()
        elif char == ":" and not inside_string and stack:
            if current_string:
                key = current_string.strip()
                current_string = ""

            if key and isinstance(stack[-1], dict):
                inside_value = True
                value = ""
                stack[-1][key] = ""

        elif (
                inside_value
                and char.strip()
                and not inside_string
                and char.strip() not in [",", "}", "]"]
        ):
            value += char

        elif inside_value and inside_string:
            pass

        elif (
                inside_value
                and value
                and not inside_string
                and char.strip() in [",", "}", "]"]
                and stack
                and isinstance(stack[-1], dict)
                and key
        ):
            if value.strip().lower() == "true":
                value = True
            elif value.strip().lower() == "false":
                value = False
            elif value.strip().lower() == "null":
                value = None
            elif reg_int.search(value.strip()):
                value = int(value)
            elif reg_float.search(value.strip()):
                value = float(value)

            stack[-1][key] = value
            key = None
            value = ""
            inside_value = False

        elif char.strip() == ",":
            if stack and isinstance(stack[-1], list):
                stack[-1].append(None)

        i += 1

    return data


if __name__ == "__main__":
    ret = judge_comment("""
        #广州电费#  公寓的空调3级能耗， 好家伙，一个月电费600块， 上班族晚上使用，这个费用，懂得都懂。 @魔方公寓 
    """)
    print(ret)
