export const WARM = {
  name: "Warm spectrum",
  c1: "#ff7a4d",
  c2: "#ffb45c",
  c3: "#2b1410",
  subs: ["settled", "open", "present"] as const,
};

export const NAV_LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#models", label: "Agents" },
  { href: "#emotions", label: "Emotions" },
  { href: "#docs", label: "Docs" },
  { href: "#safety", label: "Safety" },
];

export const STEPS = [
  {
    num: "01",
    title: "The gate",
    body: "A hardwired safety gate reads every message before anything else. It cannot be bypassed — and in a crisis, MindLens answers from vetted templates only. No model improvises.",
  },
  {
    num: "02",
    title: "The read",
    body: "A bounded graph reads the moment, recalls only relevant context, and chooses one careful response path. You see progress without being given a diagnosis.",
  },
  {
    num: "03",
    title: "The recall",
    body: "MindLens remembers what you've shared — people, deadlines, wins — and brings back only what this moment actually needs.",
  },
  {
    num: "04",
    title: "The response",
    // Not "always ending in a choice": the V2 graph deliberately drops the
    // options above 0.8 distress ("No advice. No choices."), which is the
    // right behaviour and the opposite of what the old copy promised.
    body: "The graph drafts a reply in the voice of a wise coaching friend: practical, warm, and usually ending in a choice — breathing, journaling, or just talking. When distress runs high it drops the options and just stays with you.",
  },
  {
    num: "05",
    title: "The record",
    body: "Moods and progress are logged so next week's MindLens knows what this week's you worked through — and the people and topics it picks up land in Memory, where you can change them.",
  },
];

export const AGENTS = [
  { id: "safety_gate", title: "Safety gate", body: "Deterministic crisis screening runs before any hosted model call and can exit directly to controlled templates." },
  { id: "assess", title: "Structured assessment", body: "Groq returns a constrained assessment used for routing; it never diagnoses or presents emotional certainty." },
  { id: "memory_recall", title: "Memory recall", body: "The graph selects relevant preference signals from MongoDB without placing personal memories in the vector index." },
  { id: "retrieve", title: "Hosted retrieval", body: "Pinecone searches only the curated therapy corpus and remains optional when the service is unavailable." },
  { id: "specialist", title: "Selected specialist", body: "One route writes the user-facing reply: empathy, mindfulness, journaling, reflection, routine, challenge, or distortion." },
  { id: "review", title: "Conditional reviewer", body: "Complex or high-distress turns can receive one additional safety review; ordinary turns do not pay that cost." },
  { id: "finalize", title: "Validation and delivery", body: "Controlled crisis responses and ordinary replies are validated, persisted, streamed, and returned through the existing contract." },
];

// href is the actual doc on GitHub, not the profile — each card ends in
// "Open →", a promise to open *that* file, so the link has to go there.
export const DOCS = [
  { file: "README.md", title: "The public architecture", body: "The hosted V2 architecture, graph boundaries, privacy model, deployment shape, and offline review path." },
  { file: "API.md", title: "HTTP & WebSocket contract", body: "Every endpoint, the streaming chat protocol, and how agent activity reaches the client in real time." },
  { file: "V2_HOSTED_DEPLOYMENT.md", title: "Hosted deployment runbook", body: "How Render, Vercel, Groq, Pinecone, MongoDB Atlas, and Langfuse fit together, including free-tier limitations." },
];
export const REPO_URL = "https://github.com/AmiruMallawarachchi/mindlens";

/** Rules 03, 04 and 05 each overstated something and have been narrowed to
 * what the code actually guarantees: the access token is in browser storage
 * (only the refresh token is an httpOnly cookie), the conversation
 * transcript is kept even though it isn't listed on the Memory page, and
 * the confidence figure is the classifier's real score rather than a
 * constant — it was hardcoded until the orchestrator started assigning it. */
export const RULES = [
  { num: "01", title: "Crisis answers are template-only", body: "Zero LLM calls when it matters most. Every crisis response is written and vetted by humans." },
  { num: "02", title: "The safety gate runs first, every turn", body: "No agent, prompt or feature can skip it. Safety overrides convenience — by design." },
  { num: "03", title: "Your words stay yours", body: "Every database query scoped to you, rate limits everywhere, and never sold or used for advertising. Replies are written by Groq — this turn's message goes to them with emails, phone numbers and ID numbers stripped, though your name and anyone you've mentioned go with it, because that's what makes a reply sound like it knows you." },
  { num: "04", title: "Memory is visible", body: "Your conversations are saved so next week picks up where this one left off. Anything MindLens learns from them shows up in Memory first, where you can edit or delete it." },
  { num: "05", title: "Never a diagnosis", body: "MindLens names feelings in plain language and shows how sure it is. It never labels you." },
];

export const GITHUB_URL = "https://github.com/AmiruMallawarachchi";
export const ARCHITECTURE_URL = "https://github.com/AmiruMallawarachchi/mindlens/blob/main/docs/ARCHITECTURE.md";
