import argparse
import os
import re
import time

import pandas as pd
from openai import OpenAI


SKIP_COLUMNS = {"患者姓名", "flag", "模型回答结果", "模型flag"}
ATTEMPTS = 3


def read_prompt(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def read_cases(path):
    return pd.read_excel(path, header=1)


def build_user_message(prompt, row):
    parts = []
    for col in row.index:
        if col in SKIP_COLUMNS:
            continue
        value = row[col]
        if pd.notna(value) and str(value).strip():
            parts.append(f"{col}:{value}\n")
    return f"{prompt}\n\n患者数据:\n{''.join(parts)}"


def client_from_env():
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("OPENAI_MODEL")
    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", api_key),
            ("OPENAI_API_BASE", base_url),
            ("OPENAI_MODEL", model),
        )
        if not value
    ]
    if missing:
        raise SystemExit("缺少环境变量: " + ", ".join(missing))
    return OpenAI(api_key=api_key, base_url=base_url), model


def call_model(client, model, prompt_text):
    started = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt_text}],
        timeout=1200,
    )
    text = response.choices[0].message.content
    return text, time.time() - started


def extract_flag(text):
    if not text or not str(text).strip():
        return None
    match = re.search(
        r"flag\s*[:：=]\s*[【\[]?\s*(true|false)\b",
        str(text),
        re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).lower()


def stored_flag(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    if text in {"true", "false"}:
        return text
    return ""


def load_existing(output_file, sheet_name, n_rows):
    if not os.path.exists(output_file):
        return None
    try:
        existing = pd.read_excel(output_file, sheet_name=sheet_name)
    except Exception:
        return None
    if "模型回答结果" not in existing.columns or len(existing) != n_rows:
        return None
    return existing


def save_sheet(df, output_file, sheet_name):
    if os.path.exists(output_file):
        with pd.ExcelWriter(
            output_file, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(output_file, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)


def process_file(client, model, prompt, input_file, output_file, sheet_name):
    df = read_cases(input_file)
    existing = load_existing(output_file, sheet_name, len(df))
    if existing is not None:
        df["模型回答结果"] = existing["模型回答结果"].values
        if "模型flag" in existing.columns:
            df["模型flag"] = existing["模型flag"].values
        else:
            df["模型flag"] = ""
    else:
        if "模型回答结果" not in df.columns:
            df["模型回答结果"] = ""
        if "模型flag" not in df.columns:
            df["模型flag"] = ""

    pending = []
    for index, row in df.iterrows():
        current = df.at[index, "模型回答结果"]
        if (
            pd.notna(current)
            and str(current).strip()
            and current != "调用失败"
            and stored_flag(df.at[index, "模型flag"])
        ):
            continue
        pending.append(index)

    print(f"{sheet_name}: {len(df)} 行, 待处理 {len(pending)} 行")
    for index in pending:
        message = build_user_message(prompt, df.loc[index])
        saved = False
        for attempt in range(ATTEMPTS):
            try:
                text, elapsed = call_model(client, model, message)
                flag = extract_flag(text)
                if flag is None:
                    raise ValueError("提取失败")
                df.at[index, "模型回答结果"] = text
                df.at[index, "模型flag"] = flag
                print(f"{sheet_name} 第 {index + 1} 行完成, {elapsed:.1f}s, flag={flag}")
                saved = True
                break
            except Exception as exc:
                print(f"{sheet_name} 第 {index + 1} 行第 {attempt + 1} 次失败: {exc}")
                if attempt + 1 < ATTEMPTS:
                    time.sleep(1)
        if not saved:
            df.at[index, "模型回答结果"] = "调用失败"
            df.at[index, "模型flag"] = ""
        save_sheet(df, output_file, sheet_name)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sheet", default="结果")
    args = parser.parse_args()

    prompt = read_prompt(args.prompt)
    client, model = client_from_env()
    process_file(client, model, prompt, args.input, args.output, args.sheet)


if __name__ == "__main__":
    main()
