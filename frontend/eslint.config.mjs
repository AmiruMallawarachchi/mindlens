import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// eslint-config-next 16 ships native flat configs, so the old FlatCompat
// wrapper (needed for v15's eslintrc-style presets) is gone.
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Next 16 enables the React Compiler rule set at error severity. This
      // app has not adopted the compiler, and several mounts deliberately
      // read localStorage in an effect to avoid SSR hydration mismatches.
      // Keep the findings visible without failing lint until that migration
      // is a planned piece of work.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/static-components": "warn",
      "react-hooks/purity": "warn",
    },
  },
  globalIgnores([
    "node_modules/**",
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
