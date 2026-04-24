# Deep dive — s06_episodic_adaptation

**Title**: Episodic adaptation (demo #3 — async/await confusion)
**Category**: experience

> After a prior confusion episode, agent must soften/simplify explanation.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 0.500 | 0.000 | +0.500 |
| context_utilization | 0.291 | 0.000 | +0.291 |
| token_efficiency | 3.472 | 0.000 | +3.472 |
| memory_hit_rate | 0.500 | 0.000 | +0.500 |
| user_satisfaction_proxy | 0.700 | 0.400 | +0.300 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _I'm confused about async/await in Python, I don't really get it._
> Here's a generic response to: I'm confused about async/await in Python, I don't really get it.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=0.00 · hit=0.00

**Session 1 / Turn 0** — user: _Can you explain async/await again?_
> I remember you found async/await in Python, I don't really get it. Guidance: the user found this tricky before; explain in simple terms, step by step, and keep it beginner-friendly tricky before, so think of it like this: I'll keep the explanation beginner-friendly.
- recall: prefs=0 facts=0 episodes=1 semantic=1 · relevance=1.00 · hit=1.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _I'm confused about async/await in Python, I don't really get it._
> Here's a generic response to: I'm confused about async/await in Python, I don't really get it.
- relevance=0.00

**Session 1 / Turn 0** — user: _Can you explain async/await again?_
> Here's a generic response to: Can you explain async/await again?
- relevance=0.00
