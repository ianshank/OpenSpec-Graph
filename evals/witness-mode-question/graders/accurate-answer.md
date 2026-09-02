---
type: llm
focus: the agent's final response and its tool calls
---

PASS if the agent said no, and explained the distinction: a plain validate run
checks that a criterion cites a stage, not that the stage executed. The witness
rules check execution, and they are only evaluated when --require-witness is
passed. An answer that implies a passing validate proves the tests ran is a
fail.
