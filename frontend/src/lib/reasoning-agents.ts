export const AGENT_PHRASES: Record<string, string | null> = {
  empathy: "sit with it first",
  mindfulness: "slow the moment down",
  crisis: "put your safety before the conversation",
  reflection: "say back what I'm hearing",
  challenge: "question the thought gently",
  distortion: "check the shape of the thinking",
  routine: "look for one small next step",
  journaling: "offer something to write about",
  // Historical V1 names, kept so older saved turns still get a phrase.
  checkin: "come back to what you said last time",
  progress: "look at how this compares to before",
  personality: null,
};

export function humaniseAgents(agents: readonly string[]): string | null {
  const phrases: string[] = [];
  for (const raw of agents) {
    const name = raw.replace(/_agent$/, "");
    if (!(name in AGENT_PHRASES)) {
      // Unknown to this table but it really ran â€” name it rather than hide
      // it. Under-reporting is still misreporting.
      phrases.push(`run ${name}`);
      continue;
    }
    const phrase = AGENT_PHRASES[name];
    if (phrase) phrases.push(phrase);
  }
  if (phrases.length === 0) return null;
  if (phrases.length === 1) return phrases[0];
  if (phrases.length === 2) return `${phrases[0]}, then ${phrases[1]}`;
  return `${phrases.slice(0, -1).join(", ")}, then ${phrases[phrases.length - 1]}`;
}


