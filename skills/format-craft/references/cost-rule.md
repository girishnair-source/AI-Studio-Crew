<!-- Adapted from invideoio/skills (Apache-2.0), references/cost-rule.md. Re-addressed to the AI Studio Crew; tool commands removed. -->

# Cost

Editor edits are free. Generation costs credits: price it first, say it, cap it.

- **Price first.** Run the generation with the crew tools . It checks the inputs and gives the price without spending anything.
- **Say it.** Tell the person the price before you spend it. When the price is an estimate, say so.
- **Cap it.** Run it with `the roll budget`  set to the price you said; nothing starts above the cap.
- **Once only.** Pass `a shot id`  on every generation, so a retry after a timeout finds the first run instead of paying twice.
- **Report it.** On delivery, say what you spent.
