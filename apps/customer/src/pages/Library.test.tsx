import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Job } from "@veritas/shared";
import Library from "./Library";

const fetchNextPage = vi.fn();
const state = {
  pages: [] as { jobs: Job[]; total_count: number }[],
  hasNextPage: false,
  isFetchingNextPage: false,
};

vi.mock("../services/jobsService", () => ({
  useLibrary: () => ({
    data: { pages: state.pages },
    isLoading: false,
    fetchNextPage,
    hasNextPage: state.hasNextPage,
    isFetchingNextPage: state.isFetchingNextPage,
  }),
  useStats: () => ({ data: undefined }),
}));

const job = (id: string, over: Partial<Job> = {}): Job =>
  ({
    id,
    status: "completed",
    title: id,
    assets: [],
    verified: false,
    cost_usd: 0,
    ...over,
  }) as Job;

function renderLibrary() {
  return render(
    <MemoryRouter>
      <Library />
    </MemoryRouter>,
  );
}

describe("Library", () => {
  it("shows how many runs are loaded and fetches the next page on click", () => {
    // The verified runs are the oldest, so they sit past the first page.
    state.pages = [{ jobs: [job("a"), job("b")], total_count: 30 }];
    state.hasNextPage = true;
    state.isFetchingNextPage = false;

    renderLibrary();

    expect(screen.getByText("Showing 2 of 30")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(fetchNextPage).toHaveBeenCalled();
  });

  it("flattens every loaded page into one grid", () => {
    state.pages = [
      { jobs: [job("first")], total_count: 2 },
      { jobs: [job("second", { verified: true })], total_count: 2 },
    ];
    state.hasNextPage = false;

    renderLibrary();

    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
    expect(screen.getByText("✓ Verified")).toBeInTheDocument();
  });

  it("hides the control once the last page is loaded", () => {
    state.pages = [{ jobs: [job("only")], total_count: 1 }];
    state.hasNextPage = false;

    renderLibrary();

    expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
    expect(screen.queryByText(/^Showing/)).toBeNull();
  });

  it("disables the control while the next page is in flight", () => {
    state.pages = [{ jobs: [job("a")], total_count: 30 }];
    state.hasNextPage = true;
    state.isFetchingNextPage = true;

    renderLibrary();

    expect(screen.getByRole("button", { name: "Loading…" })).toBeDisabled();
  });

  it("shows the empty state when there are no runs", () => {
    state.pages = [{ jobs: [], total_count: 0 }];
    state.hasNextPage = false;

    renderLibrary();

    expect(screen.getByText(/No runs yet/)).toBeInTheDocument();
  });
});
