import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Login from "./Login";

describe("Login", () => {
  it("shows the password field and sign-in button (empty state)", () => {
    render(<Login />);
    expect(screen.getByPlaceholderText("Enter admin password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});
