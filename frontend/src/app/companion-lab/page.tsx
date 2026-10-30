import { notFound } from "next/navigation";
import { CompanionLab } from "./companion-lab";

/** Dev-only grid for checking every companion in every activity state.
 * Production returns a 404 so the route cannot be crawled or mistaken for
 * a product surface. */
export default function Page() {
  if (process.env.NODE_ENV === "production") notFound();
  return <CompanionLab />;
}
