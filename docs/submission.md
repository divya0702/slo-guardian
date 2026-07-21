# SLO Guardian

## Inspiration

Picture an online store during a busy sale. Checkout suddenly slows down. Engineers can see *that* something is wrong, but not *why*, or which fix is actually safe to try. Guess wrong, and you can break checkout worse than the original problem.

We kept coming back to one worry about AI in these moments: it's great at guessing what might help, but a guess is not the same as permission to act. So we built a system with a simple rule at its core:

> **GPT proposes. The rules decide. The human approves.**

## What it does

SLO Guardian watches a small online store (checkout, inventory, pricing, and recommendations) for trouble. When something starts failing, it:

1. **Explains it** — shows exactly what's slow and why, in plain terms, backed by real trace data.
2. **Asks GPT-5.6 for ideas** — the AI reads that evidence and suggests three possible fixes.
3. **Checks every idea itself** — our own code rejects anything unsafe, untrue, or unproven, and tests the rest in a safe practice run.
4. **Waits for a person** — only a human can look at the results and press approve. The fix then switches off automatically after a short window.

The AI never touches the real system. It can only suggest.

## How we built it

- A small practice online store with five services, so we can safely break things on purpose.
- Live tracing that shows exactly what's slow and why.
- GPT-5.6, working through the AI assistant the operator is already signed into — not a hidden API key baked into the app.
- Our own safety layer that checks, tests, and ranks every suggestion before anything is shown as "ready."
- A simple dashboard where a person reviews the evidence and clicks approve.

## Challenges we faced

The hard part was never getting the AI to suggest something — it was catching suggestions that *sound* reasonable but aren't actually safe. A few tricky ones:

- Ideas that reference evidence that doesn't exist.
- Ideas that would fix the small problem by breaking something critical.
- Making sure rejected ideas stay visible with a clear reason, instead of quietly disappearing.

We also decided early on that the AI should never hold the keys to the system itself, which meant building the whole approval step as something only a human can do — on purpose, not just by convention.

## Accomplishments we're proud of

- Checkout recovery time dropped from about **1,163 ms to 382 ms** in our test scenario.
- **Zero** critical requests were ever dropped, even while fixing the problem.
- Every fix is tested in a safe practice run before a human ever sees an approve button.

## What we learned

The most useful role for AI here wasn't making the final call — it was turning a messy, stressful incident into a clear explanation and a short list of options a person can actually evaluate quickly. Real trust doesn't come from asking the AI to be careful; it comes from never giving it the ability to act alone in the first place.

## What's next

Right now, SLO Guardian only practices on our own test store. Next, we want to connect it to real systems, add proper logins and permissions, and let it learn from real past incidents — while keeping the same rule at the center: AI explains and suggests, our code checks and measures, and a person always makes the final call.
