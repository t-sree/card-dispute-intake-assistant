# Card Dispute Intake Assistant

*An AI assistant that helps bank agents capture complete card disputes on the first conversation*

---

## 1. Problem statement

When a customer contacts their bank about a card charge they don't recognize or a purchase that went wrong, a customer service agent must turn that conversation into a complete dispute case.

This is harder than it looks, because **each type of dispute needs different information**:

- A simple fraud claim ("I didn't make this charge") needs only a few facts.
- A merchant dispute ("I returned the item but never got my refund") needs more: return date, merchant contact attempts, and supporting details.

Agents handle many topics, often several chats at once, and can't remember every rule. Bank of America described this exact struggle: before its AI assistant, agents had to listen to customers while searching for policies, procedures, and next steps at the same time.

As a result, agents either:
- **ask too few questions**, creating incomplete cases that need follow-up, delay resolution, or fail when the bank tries to recover money from the merchant, or
- **ask too many questions**, slowing down simple cases and frustrating customers who are already stressed.

**In one sentence:**
> Dispute cases are often created incomplete or inefficiently because agents must work out, in real time, what each type of dispute requires.

---

## 2. What we are building

**An assistant that sits beside the agent during a chat with the customer.** It:

1. **Understands the dispute.** It reads the conversation, identifies the dispute type, and pulls out facts already mentioned, such as merchant, amount, and date. If the customer mentions two problems, it creates two separate cases.
2. **Checks what's missing.** It compares the facts against a checklist of required information for that dispute type, based on card network rules and credit card regulations.
3. **Suggests only the next necessary question.** It stops as soon as the case is complete. Simple fraud claims finish quickly. Merchant disputes get deeper questions. If warning signs appear, such as a dispute right after a forgotten subscription renewal, it suggests one or two extra questions.
4. **Clears up confusion using account data.** For example: *"This charge matches the customer's subscription that renewed on the 5th."* Sometimes this resolves the issue without a dispute.
5. **Produces a complete case** at the end, with dispute type, facts, reason code, and deadlines, for the agent to review and confirm.

**The agent stays in control.** The AI suggests; the human decides.

**Key design rule:** *The LLM reads, code decides.* The AI only understands the conversation. Checklists, reason codes, and deadline calculations are plain code, so every result is predictable, testable, and explainable.

---

## 3. What needs to be done

**Step 1: Dispute checklist (foundation)**
Define 5–6 common dispute types and the required information for each, based on public card network rules and Regulation Z.

**Step 2: Data**
- **Real customer language:** Credit card complaints from the CFPB's public complaint database.
- **Synthetic account data:** A script that generates realistic transactions for each customer.
- **Simulated conversations:** One LLM plays the customer, using only facts from a real complaint.

**Step 3: Core engine**
Extraction of facts and dispute type, the "what's missing" checker, the next-question logic, and the deadline and reason-code rules.

**Step 4: Agent screen**
A simple chat interface: the conversation on one side, the assistant's suggestions, extracted facts, and missing items on the other.

**Step 5: Evaluation**
Hand-label 50–100 cases and measure:
- Was the case complete?
- Were the dispute type and reason code correct?
- How many questions did it take?
- Were any questions unnecessary?

**Step 6: Presentation**
A clear README, an architecture diagram, results, limitations, and a 2–3 minute demo video.

**Rough timeline:** 5–6 weeks part-time.

---

## 4. How it relates to real-world business

**Major banks are investing in exactly this kind of tool:**

- **Bank of America** enhanced EricaAssist in July 2026, a human-assisted AI agent used by more than 18,000 customer service representatives during client conversations. It summarizes why a client is calling and recommends next steps without interrupting the conversation.
- **U.S. Bank** described a customer seeing an unrecognized transaction in the app and connecting to a live agent, calling the situation stressful and stressing that agents must quickly reassure customers and walk them through the process. That's exactly our main use case.
- **Capital One** built a multi-agent workflow for fraud customer service that handles millions of calls a year, starting with an "understanding agent" that identifies the customer's intent.

**Vendors sell this capability too.** FIS's dispute product guides agents through intake questions, suggests next actions, and prompts reason codes. This proves banks pay to solve the problem.

**The open-source gap:** Several individuals have published dispute AI projects on GitHub, but they all work on investigating and deciding cases *after* they're created. None helps during the conversation itself.

**Where our project fits:** It's a small, focused, open version of one piece of what these banks are building. We don't compete with their systems; we demonstrate understanding of their problem.

---

## 5. Business impact

**The scale is large.** Visa alone reports processing 106 million disputes in a year.

**Each dispute costs banks money.** Mastercard estimates financial institutions lose about $9 to $10 per dispute, mostly from labor and fraud control. Another estimate puts issuers' share of each chargeback at about $37. A small institution with $200 million in payment volume might handle around 11,000 chargeback cases a year at a cost of about $400,000, mostly operational spend.

**Where our tool creates value:**

| Value | How |
|---|---|
| **Less rework** | Complete cases on first contact mean fewer follow-ups and less analyst time |
| **Fewer unnecessary chargebacks** | Consumers skip the merchant in 75% of disputes; our tool asks whether the merchant was contacted and clears up confusion like unrecognized subscriptions |
| **Earlier friendly fraud signals** | About 20% of disputes are linked to first-party fraud; we flag warning signs without accusing honest customers |
| **Faster simple cases** | Right-sized questioning keeps easy cases quick and customers satisfied |
| **Consistency** | Every agent asks the right questions, regardless of experience |

**Honest note:** This is a portfolio project, so it won't produce measured bank savings. Impact should be presented as clearly labeled estimates. For example: *"If better intake avoids one follow-up on 20% of 11,000 annual cases, that's 2,200 fewer follow-ups."*

---

## 6. One-line summary

> **Card Dispute Intake Assistant helps bank agents collect a complete dispute case in the first conversation by suggesting only the questions each dispute actually needs: fast for simple cases, thorough for complex ones. It's a focused version of the agent-assist AI that banks like Bank of America and Capital One are investing in today.**
