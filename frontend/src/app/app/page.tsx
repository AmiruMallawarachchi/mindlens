import { Suspense } from "react";
import { MindLensApp } from "@/components/mindlens-app";

export default function AppPage() {
  // MindLensApp reads ?auth=register via useSearchParams (Home's "Sign up"
  // link) — Next requires that behind a Suspense boundary during static
  // generation.
  return (
    <Suspense fallback={null}>
      <MindLensApp />
    </Suspense>
  );
}
