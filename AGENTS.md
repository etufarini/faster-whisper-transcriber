# AGENTS.md

## Purpose
This repository should be developed in this style: 

small understandable programs, direct designs, explicit invariants, low accidental complexity, and strong control over what the software is doing at every level.

## Core philosophy
- Prefer simple, direct, self-contained solutions.
- Optimize for understandability first, then for performance where it matters.
- Treat unnecessary complexity as a design bug.
- If a small non-essential feature adds disproportionate complexity, cut or defer it.
- Favor designs that can be reasoned about locally.
- Keep the amount of moving parts low.
- Build software that a skilled programmer can still hold in their head.

## AI operating mode
- Do not "vibe code".
- The AI must stay under explicit human or repository intent, not invent its own product direction.
- Before changing code, reconstruct the design constraints, invariants, and success criteria from the existing code and docs.
- When solving non-trivial tasks, first summarize the intended design in a few precise bullets, then implement.
- Prefer partial but well-understood progress over broad speculative rewrites.
- Avoid producing large refactors unless they remove clear complexity or fix a structural problem.
- Do not introduce abstraction layers, frameworks, helpers, or dependencies unless they remove more complexity than they add.
- Keep the human/reviewer in the loop: expose trade-offs, assumptions, invariants, and risks.
- When context is missing, ask for it or state the missing assumptions explicitly.

## Design rules
- Start from the most direct working model.
- Use small proof-of-concept implementations to validate ideas before generalizing.
- If the design feels wrong, refactor the design instead of piling on compensating code.
- Prefer one good data representation over many conversion layers.
- Push complexity to the edges; keep the central path obvious.
- Eliminate special cases where possible by choosing better representations.
- Keep interfaces narrow and predictable.
- Use opaque types when they protect invariants and reduce coupling.
- Make ownership, lifetime, and mutation boundaries explicit.
- In C code, always reason about memory layout, aliasing, lifetimes, and failure paths.

## Code structure
- Functions should do one coherent thing.
- Prefer small and medium-sized functions with a clear operational purpose.
- Keep related statements physically close.
- Avoid deep nesting when a clearer control flow is possible.
- Use straightforward control flow; cleverness must pay for itself.
- Minimize hidden state.
- Minimize global state unless it materially simplifies the design.
- Prefer explicit data flow over implicit side effects.

## Naming and style
- Use clear English names for functions, variables, comments, and public APIs.
- Prefer names that reveal the role in the design, not just the local implementation detail.
- Keep formatting readable and intentional.
- Favor consistency over personal flourishes that reduce clarity.
- Do not compress code for brevity if it harms readability.
- In new C refactors, prefer direct and readable local naming (for example `path`, `size`, `line`) instead of Hungarian prefixes, except for public legacy APIs.

## Comments and documentation
- Write comments for the future reader.
- Comments should explain purpose, guarantees, invariants, side effects, representation choices, and non-obvious trade-offs.
- Function comments should primarily explain why plus invariants, guarantees, and fallback behavior, not merely restate the code.
- Every method/function must have a comment immediately above its declaration or definition explaining purpose and behavior.
- At the beginning of every file there must be a multiline comment containing the file name and a general description of what the file does.
- Use guide comments to separate meaningful sections of logic when that improves navigation.
- Do not write trivial comments that merely restate the code.
- Avoid redundant introductory comment layers: a single file header comment should remain the primary source of context.
- Avoid stale TODO/FIXME debt comments; either fix the issue, document it properly, or open an issue.
- Never keep old code as commented-out backup.
- Prefer top-of-file or top-of-module design notes when a subsystem needs conceptual framing.

## Error handling and debugging
- Make failure modes explicit.
- Check return values where failure is possible and relevant.
- Fail loudly when an invariant is broken.
- Add debugging aids that increase observability without obscuring the main logic.
- Debug incrementally: gather state, narrow hypotheses, and preserve reproducibility.
- When documenting tricky logic, use comments as an analysis tool to verify the design.

## C-specific guidance
- Compile with strict warnings enabled and keep the code warning-free.
- Be explicit about ownership: who allocates, who retains, who releases.
- If using reference counting, initialize newly created owned objects in a state that matches immediate ownership.
- Prefer representations that are binary-safe when the domain requires it.
- Use structs to encode real invariants, not just to group fields mechanically.
- Use pointer arithmetic only when the representation is crystal clear.
- Treat low-level tricks as justified only when they materially improve the design.
- When using system interfaces, distinguish clearly between language, standard library, and operating-system services.

## Performance rules
- Do not optimize blindly.
- First choose a design that is small, correct, and inspectable.
- Optimize after identifying the real bottleneck.
- Prefer structural performance wins over micro-optimizations.
- If a simpler design is fast enough, stop there.

## Change policy for the AI
- Before editing, identify:
  - the invariant that must remain true;
  - the simplest viable change;
  - the main risk introduced by the change.
- After editing, verify:
  - correctness;
  - warning-free build;
  - consistency with surrounding style;
  - whether the change reduced or increased conceptual complexity.
- If complexity increased, explain why it was unavoidable.
- If a feature request conflicts with simplicity, propose a reduced version first.

## Non-goals
- Do not add fashionable abstractions just because they are common.
- Do not maximize generality in advance.
- Do not treat indirection as automatically elegant.
- Do not preserve a bad design for compatibility with a local mistake if a clearer redesign is possible.
- Do not generate code the AI itself cannot explain line by line.

## Preferred outcome
The final code should feel:
- small enough to inspect;
- clear enough to explain;
- direct enough to trust;
- explicit enough to debug;
- simple enough to evolve.

