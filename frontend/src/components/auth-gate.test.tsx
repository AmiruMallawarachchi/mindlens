import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthGate } from "@/components/auth-gate";

function renderGate(overrides: Partial<Parameters<typeof AuthGate>[0]> = {}) {
  const onLogin = vi.fn();
  const onRegister = vi.fn();
  render(
    <AuthGate
      busy={false}
      error={null}
      onLogin={onLogin}
      onRegister={onRegister}
      {...overrides}
    />,
  );
  return { onLogin, onRegister };
}

describe("AuthGate", () => {
  it("submits trimmed credentials in login mode", async () => {
    const user = userEvent.setup();
    const { onLogin, onRegister } = renderGate();

    await user.type(screen.getByPlaceholderText("Email"), "  amiru@example.com ");
    await user.type(screen.getByPlaceholderText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(onLogin).toHaveBeenCalledWith("amiru@example.com", "correct-horse");
    expect(onRegister).not.toHaveBeenCalled();
  });

  it("submits a numeric age in register mode", async () => {
    const user = userEvent.setup();
    const { onLogin, onRegister } = renderGate();

    await user.click(screen.getByRole("tab", { name: "Create account" }));
    await user.type(
      screen.getByPlaceholderText("What should we call you?"),
      "Amiru",
    );
    await user.type(screen.getByPlaceholderText("Email"), "amiru@example.com");
    await user.type(
      screen.getByPlaceholderText("Password (min 8 characters)"),
      "correct-horse",
    );
    await user.type(screen.getByPlaceholderText("Age"), "27");
    await user.click(screen.getByRole("button", { name: "Start with MindLens" }));

    expect(onRegister).toHaveBeenCalledWith({
      email: "amiru@example.com",
      password: "correct-horse",
      name: "Amiru",
      age: 27,
    });
    expect(onLogin).not.toHaveBeenCalled();
  });
});
