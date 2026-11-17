# Imaging–pathology qualitative comparison

One user message is sent for each case. It contains the full prompt, then the imaging report and the pathology report. There is no system message. Temperature, top_p, and max tokens are not set in the request.

The prompt used for the reported results is `prompts/prompt_zh.txt`. `prompts/prompt_en.txt` is a translation of that prompt, including the operational rules and the worked examples.

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=...
export OPENAI_API_BASE=...
export OPENAI_MODEL=...
python infer.py --prompt prompts/prompt_zh.txt --input cases.xlsx --output results.xlsx
```

Input workbooks use the second row as the header. Columns other than `患者姓名`, `flag`, `模型回答结果`, and `模型flag` are pasted into the user message. Each case is sent at most 3 times. The reply is kept only when `flag` is `true` or `false`; that value is written to `模型flag`, and the full reply stays in `模型回答结果`. If the call fails or `flag` cannot be read, the answer cell is `调用失败`. A finished row is skipped on the next run. A row left as `调用失败` is sent again.

## Example

`examples/input.txt` is one complete user message. `examples/output.txt` is the text returned for that message. The case has no name attached.

## WiNGPT-3.5

WiNGPT-3.5 is a medical vertical model based on Qwen3, at the 30B-A3B scale. It is trained on medical literature, guidelines, and clinical instructions, and is aligned for medical question answering and clinical text. Medical text is restated and mixed with instruction data in one MIP stage. Supervised fine-tuning uses DeepSpeed ZeRO-3 and AdamW for 2 epochs, with a learning rate of 3×10⁻⁶, a 150-step linear warmup, and cosine decay to 10% of the initial rate. Reinforcement learning uses GRPO in the Verl framework, with 128 samples per step and 12 rollouts per prompt. Alignment then uses a two-stage generative reward: continuous scores, followed by binary scores with GSPO.

Weights: https://drive.google.com/drive/folders/19g-RlPjTOPfqFeBRNGxeQXKXkF3KJqxZ?usp=drive_link
