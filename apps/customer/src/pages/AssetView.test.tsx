import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Job } from "@veritas/shared";
import AssetView from "./AssetView";

function makeJob(assets: Job["assets"]): Job {
  return {
    id: "j1",
    status: "completed",
    stage: null,
    title: "Test Reel",
    error: null,
    run_id: null,
    parent_run_id: null,
    manifest_uri: null,
    manifest_hash: null,
    verified: true,
    cost_usd: 0,
    created_at: null,
    assets,
  } as Job;
}

const asset = (over: Partial<Job["assets"][number]>): Job["assets"][number] => ({
  id: "a",
  step_index: 0,
  modality: null,
  provider: null,
  model: null,
  url: null,
  sha256: null,
  media_type: null,
  ...over,
});

describe("AssetView", () => {
  it("renders an image and a voiceover for image+audio assets (main path)", () => {
    render(
      <AssetView
        job={makeJob([
          asset({
            step_index: 0,
            modality: "image",
            url: "http://x/i.jpg",
            media_type: "image/jpeg",
          }),
          asset({
            step_index: 2,
            modality: "audio",
            url: "http://x/a.mp3",
            media_type: "audio/mpeg",
          }),
        ])}
      />,
    );
    expect(screen.getByAltText("Test Reel")).toBeInTheDocument();
    expect(screen.getByText("Voiceover")).toBeInTheDocument();
  });

  it("renders no media when there are no assets (empty state)", () => {
    const { container } = render(<AssetView job={makeJob([])} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("video")).toBeNull();
  });
});
