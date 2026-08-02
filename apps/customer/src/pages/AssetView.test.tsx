import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Job } from "@veritas/shared";
import AssetView from "./AssetView";
import { voiceoverRate } from "../lib/voiceover";

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

describe("voiceoverRate", () => {
  it("compresses a voiceover that outruns the clip", () => {
    // The shipped water-bottle clip: 9.89s of speech over 5.1s of picture.
    expect(voiceoverRate(9.89, 5.1)).toBeCloseTo(1.94, 2);
  });

  it("never stretches a voiceover shorter than the clip", () => {
    // Slowing a read below 1x makes it drawl; it should just finish early.
    expect(voiceoverRate(4.0, 5.1)).toBe(1);
    expect(voiceoverRate(0.5, 10)).toBe(1);
  });

  it("falls back to natural speed before durations are known", () => {
    expect(voiceoverRate(NaN, 5)).toBe(1);
    expect(voiceoverRate(9, 0)).toBe(1);
    expect(voiceoverRate(Infinity, 5)).toBe(1);
  });

  it("stays inside the browser's legal playback range", () => {
    expect(voiceoverRate(1000, 0.01)).toBeLessThanOrEqual(16);
  });
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

  it("hides the separate voiceover player when the clip has video (paired)", () => {
    const { container } = render(
      <AssetView
        job={makeJob([
          asset({ step_index: 1, modality: "video", url: "http://x/v.mp4", media_type: "video/mp4" }),
          asset({ step_index: 2, modality: "audio", url: "http://x/a.mp3", media_type: "audio/mpeg" }),
        ])}
      />,
    );
    // The video's own controls drive the voiceover — there must be no second
    // player for the user to press.
    expect(screen.queryByText("Voiceover")).toBeNull();
    const audio = container.querySelector("audio");
    expect(audio).not.toBeNull();
    expect(audio).toHaveClass("hidden");
    expect(container.querySelector("video")).toHaveAttribute("controls");
  });

  it("renders no media when there are no assets (empty state)", () => {
    const { container } = render(<AssetView job={makeJob([])} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("video")).toBeNull();
  });
});
