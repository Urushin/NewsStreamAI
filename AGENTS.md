# Atlas AI router

Read `docs/ai/index.md`, then only the linked page relevant to the task.

- Use minimum necessary context: targeted search, relevant ranges, no full-repo scans. Exclude `data/`, `build/`, `ios/build_derived_data/`, caches, vendors, and secrets unless explicitly required.
- Do not reread unchanged files, dump large output, edit unrelated modules, or perform speculative refactors.
- Split important independent work; give subagents only required files/symbols and return compact summaries. Avoid delegation when coordination costs more than the task.
- Run the narrowest relevant test before any broad suite. Stop and report if scope grows materially.
- Cheapest capable model first: Gemini Flash or Sol Low → Sol Medium → Sol High → Astra Low → Astra Medium.
- Astra High, XHigh, Max, or Ultra require explicit user authorization. Never select them automatically.
- Use Gemini for large read-heavy exploration, summaries, docs, and logs; Codex for implementation and rigorous review.
