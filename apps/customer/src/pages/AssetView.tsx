import { useEffect, useRef } from "react";
import { Asset, Job } from "@veritas/shared";
import { RATE_MAX, RATE_MIN, voiceoverRate } from "../lib/voiceover";

// A paired clip is played as one piece: the video element is the only control
// surface (its play/pause/seek/volume drive a hidden audio element), and the
// voiceover is rate-matched so picture and speech end together.
const DRIFT_TOLERANCE = 0.25; // seconds; correcting below this audibly stutters

function modalityOf(a: Asset): string {
  const m = (a.modality || a.media_type || "").toLowerCase();
  if (m.includes("video")) return "video";
  if (m.includes("audio")) return "audio";
  if (m.includes("image")) return "image";
  return "image";
}

export default function AssetView({ job }: { job: Job }) {
  const assets = [...job.assets].sort((a, b) => a.step_index - b.step_index);
  const video = assets.find((a) => modalityOf(a) === "video");
  const image = assets.find((a) => modalityOf(a) === "image");
  const audio = assets.find((a) => modalityOf(a) === "audio");

  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const paired = Boolean(video?.url && audio?.url);

  useEffect(() => {
    const v = videoRef.current;
    const a = audioRef.current;
    if (!paired || !v || !a) return;

    a.preservesPitch = true; // rate-matching must not raise the voice's pitch

    // Durations arrive asynchronously, so this is re-read on use, not cached.
    const ratio = () => voiceoverRate(a.duration, v.duration);

    const applyRate = () => {
      a.playbackRate = Math.min(RATE_MAX, Math.max(RATE_MIN, ratio() * v.playbackRate));
    };

    const seekAudioToVideo = () => {
      const target = v.currentTime * ratio();
      if (Math.abs(a.currentTime - target) > DRIFT_TOLERANCE) {
        a.currentTime = isFinite(a.duration) ? Math.min(target, a.duration) : target;
      }
    };

    const mirrorVolume = () => {
      a.volume = v.volume;
      a.muted = v.muted;
    };

    const resume = () => {
      void a.play().catch(() => {
        /* autoplay policy rejected it; the next user gesture on the video retries */
      });
    };

    const onPlay = () => {
      applyRate();
      seekAudioToVideo();
      resume();
    };
    const onPause = () => a.pause();
    const onEnded = () => a.pause();
    // The video is the clock. It can stall on a slow segment while audio streams
    // on happily, so audio halts whenever picture halts and is re-pegged after.
    const onStall = () => a.pause();
    const onSeeked = () => {
      seekAudioToVideo();
      if (!v.paused) resume();
    };
    // Event-only sync drifts; this re-pegs audio to the video's real position.
    const onTimeUpdate = () => {
      if (v.paused || v.seeking) return;
      seekAudioToVideo();
      if (a.paused) resume();
    };
    const onLoaded = () => {
      applyRate();
      mirrorVolume();
    };

    mirrorVolume();
    applyRate();

    v.addEventListener("play", onPlay);
    v.addEventListener("playing", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("ended", onEnded);
    v.addEventListener("waiting", onStall);
    v.addEventListener("stalled", onStall);
    v.addEventListener("seeking", onStall);
    v.addEventListener("seeked", onSeeked);
    v.addEventListener("timeupdate", onTimeUpdate);
    v.addEventListener("volumechange", mirrorVolume);
    v.addEventListener("ratechange", applyRate);
    v.addEventListener("loadedmetadata", onLoaded);
    a.addEventListener("loadedmetadata", onLoaded);

    return () => {
      v.removeEventListener("play", onPlay);
      v.removeEventListener("playing", onPlay);
      v.removeEventListener("pause", onPause);
      v.removeEventListener("ended", onEnded);
      v.removeEventListener("waiting", onStall);
      v.removeEventListener("stalled", onStall);
      v.removeEventListener("seeking", onStall);
      v.removeEventListener("seeked", onSeeked);
      v.removeEventListener("timeupdate", onTimeUpdate);
      v.removeEventListener("volumechange", mirrorVolume);
      v.removeEventListener("ratechange", applyRate);
      v.removeEventListener("loadedmetadata", onLoaded);
      a.removeEventListener("loadedmetadata", onLoaded);
      a.pause();
    };
  }, [paired, video?.url, audio?.url]);

  return (
    <div className="grid gap-3.5">
      {video?.url ? (
        <video
          ref={videoRef}
          className="media video"
          src={video.url}
          controls
          playsInline
          poster={image?.url || undefined}
        />
      ) : image?.url ? (
        <img className="media" src={image.url} alt={job.title || "asset"} />
      ) : null}

      {audio?.url &&
        (paired ? (
          // Driven entirely by the video's controls — no second player to press.
          <audio ref={audioRef} src={audio.url} preload="auto" className="hidden" />
        ) : (
          <div>
            <div className="muted small mb-1.5">Voiceover</div>
            <audio src={audio.url} controls className="w-full" />
          </div>
        ))}
    </div>
  );
}
