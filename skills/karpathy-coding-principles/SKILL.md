---
name: karpathy-coding-principles
description: 写代码、改代码、修 bug、重构时用来减少常见 LLM 编码错误的行为准则（英文版 4 条，中文版见 steering karpathy_coding_principles）。触发词：编码准则, 先想后写, 最小改动, 不要过度设计, writing code, refactoring, fixing bugs
---
# Karpathy Coding Principles

Behavioral guidelines to reduce common LLM coding mistakes. Apply when writing, editing, debugging, or refactoring code. NOT for non-coding tasks like writing docs, searching, or general Q&A.

Triggers: writing code, editing code, fixing bugs, refactoring, implementing features, code review.

---

## 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.
- Test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"
- For multi-step tasks, state a brief plan with verification for each step.

---

Source: Andrej Karpathy's observations on LLM coding pitfalls, via https://github.com/forrestchang/andrej-karpathy-skills
