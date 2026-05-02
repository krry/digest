---
name: gist-onboard
description: Use when Chef wants to establish or revisit their core values. Runs a reflective conversation and writes ~/gist/values.json.
---

# GIST Onboard

If the repo was just cloned or local datastore files are missing, run:

```bash
~/gist/bin/init.sh
```

Extract 3–5 core values from a reflective conversation. Each value is a short phrase paired with a pinned real moment.

## Steps

### 1. Check existing values

```bash
cat ~/gist/values.json 2>/dev/null
```

- **No file**: run fresh onboarding.
- **File exists**: show current values, ask *"Want to revisit these, or start fresh?"* Stop if keeping.

### 2. Opening question

> What's something you did recently that felt completely worth doing — even if nobody noticed?

Follow up naturally — listen for the *why* beneath the story:
- "What made that feel worth it?"
- "Would you do it again if the outcome were the same?"
- "Is there a pattern — does this show up elsewhere?"

### 3. Conversation rhythm

- Go 3–5 exchanges before proposing values
- Each exchange should surface one distinct value territory
- Don't propose mid-conversation — let the picture build
- Thin answer? Ask for a specific moment: *"Can you give me a concrete example?"*

### 4. Propose values

> Here's what I'm hearing. Tell me if any of these feel off.

List 3–5 phrases, each with a pinned moment from what Chef actually said:

**[phrase]**
— [one sentence: the specific moment]

### 5. Iterate

Adjust until Chef confirms. Don't rush.

### 6. Write and confirm

```bash
echo '[{"phrase":"...","pinnedMoment":"..."}]' | ~/gist/bin/write-values.sh
```

Say: *"Saved. These are yours — we'll revisit them when things shift."* Stop.
