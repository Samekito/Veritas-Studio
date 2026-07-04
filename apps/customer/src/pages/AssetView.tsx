import { Asset, Job } from "@veritas/shared";

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

  return (
    <div className="grid gap-3.5">
      {video?.url ? (
        <video
          className="media video"
          src={video.url}
          controls
          playsInline
          poster={image?.url || undefined}
        />
      ) : image?.url ? (
        <img className="media" src={image.url} alt={job.title || "asset"} />
      ) : null}

      {audio?.url && (
        <div>
          <div className="muted small mb-1.5">Voiceover</div>
          <audio src={audio.url} controls className="w-full" />
        </div>
      )}
    </div>
  );
}
