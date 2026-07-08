import { existsSync, readFileSync } from "fs";
import { join } from "path";

/**
 * Merge bms/tests/qa/test-case-executions.json into QA test case execution configs.
 * Called from qa-agent during `qa:execute`.
 */
export function applyExecutionOverrides(testCases, projectRoot) {
  const path = join(projectRoot, "tests", "qa", "test-case-executions.json");
  if (!existsSync(path)) {
    return testCases;
  }

  let overrides;
  try {
    overrides = JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return testCases;
  }

  return testCases.map((tc) => {
    const override = overrides[tc.testCaseId];
    if (!override) {
      return tc;
    }
    return {
      ...tc,
      execution: {
        ...tc.execution,
        ...override,
        type: override.type || tc.execution?.type || "db",
      },
    };
  });
}
