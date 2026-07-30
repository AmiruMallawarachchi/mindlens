/**
 * The companion cast — design project "Mindlens System", turn "cast":
 * "Approved. These ten and no others." Nimbus is the default chat
 * companion; the other nine are alternate shapes a user can pick as their
 * default in Your Mindlens, then rename to whatever they like.
 *
 * Every shape's colour is bound to --e1/--e2/--e3 from the active emotion
 * (Anchor is the deliberate exception — "colourless" per its own
 * description), matching how Nimbus itself already works.
 */

export type CompanionShape =
  | "cloud"
  | "dot"
  | "flame"
  | "jelly"
  | "frond"
  | "sphere"
  | "square"
  | "bell"
  | "crescent"
  | "star";

export type CompanionId =
  | "nimbus"
  | "flit"
  | "ember"
  | "tide"
  | "fern"
  | "lens"
  | "anchor"
  | "lantern"
  | "luna"
  | "comet";

export interface CompanionDef {
  id: CompanionId;
  name: string;
  tagline: string;
  shape: CompanionShape;
}

export const COMPANIONS: CompanionDef[] = [
  { id: "nimbus", name: "Nimbus", tagline: "The steady friend — the main chat companion.", shape: "cloud" },
  { id: "flit", name: "Flit", tagline: "A firefly. Lands on the sentence that matters.", shape: "dot" },
  { id: "ember", name: "Ember", tagline: "A kept flame. Makes anger feel allowed.", shape: "flame" },
  { id: "tide", name: "Tide", tagline: "Rises and drains with distress — watch yourself calm down.", shape: "jelly" },
  { id: "fern", name: "Fern", tagline: "A frond per check-in. Progress you can't fail at.", shape: "frond" },
  { id: "lens", name: "The Lens", tagline: "A faceless glass sphere. The grown-up option.", shape: "sphere" },
  { id: "anchor", name: "Anchor", tagline: "Colourless and deliberately still — no spectacle.", shape: "square" },
  { id: "lantern", name: "Lantern", tagline: "Glows at the pace it wants you to breathe.", shape: "bell" },
  { id: "luna", name: "Luna", tagline: "The late-night one. Insomnia and 2am spirals.", shape: "crescent" },
  { id: "comet", name: "Comet", tagline: "Turns up for wins — the celebration made into a creature.", shape: "star" },
];

export const DEFAULT_COMPANION_ID: CompanionId = "nimbus";

export function getCompanion(id: string | null | undefined): CompanionDef {
  return COMPANIONS.find((c) => c.id === id) ?? COMPANIONS[0];
}
