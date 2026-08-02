import { Link } from "react-router-dom";
import { useLibrary, useStats } from "../services/jobsService";

export default function Library() {
  const {
    data,
    isLoading: loading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useLibrary();
  const { data: stats } = useStats();
  const jobs = data?.pages.flatMap((page) => page.jobs) ?? [];
  const totalCount = data?.pages[0]?.total_count ?? 0;

  return (
    <div className="container wide">
      <h1 className="text-3xl tracking-[-0.5px]">Asset Library</h1>
      <p className="muted">Every run is stored on Backblaze B2 with its provenance manifest.</p>

      {stats && (
        <div className="stat-grid mb-7.5 mt-5.5">
          <div className="stat">
            <div className="n">{stats.runs}</div>
            <div className="l">Runs</div>
          </div>
          <div className="stat">
            <div className="n">{stats.assets}</div>
            <div className="l">Assets on B2</div>
          </div>
          <div className="stat">
            <div className="n">{stats.verified}</div>
            <div className="l">Verified</div>
          </div>
          <div className="stat">
            <div className="n">${stats.total_cost_usd}</div>
            <div className="l">Total gen cost</div>
          </div>
        </div>
      )}

      {loading && <p className="muted">Loading…</p>}
      {!loading && jobs.length === 0 && (
        <div className="card">
          <p className="muted m-0">
            No runs yet. <Link to="/">Create your first clip →</Link>
          </p>
        </div>
      )}

      <div className="grid cols">
        {jobs.map((job) => {
          const img = job.assets.find((a) => (a.modality || "").includes("image"));
          const vid = job.assets.find((a) => (a.modality || "").includes("video"));
          return (
            <Link key={job.id} to={`/passport/${job.id}`} className="asset-card">
              {vid?.url ? (
                <video
                  className="media video"
                  src={vid.url}
                  muted
                  playsInline
                  preload="metadata"
                  poster={img?.url || undefined}
                />
              ) : img?.url ? (
                <img className="media aspect-video object-cover" src={img.url} />
              ) : (
                <div className="media video grid place-items-center">
                  <span className="muted small">
                    {job.status === "failed" ? "Failed" : "Processing…"}
                  </span>
                </div>
              )}
              <div className="body">
                <div className="spread">
                  <div className="title">{job.title || job.id}</div>
                </div>
                <div className="row mt-2">
                  {job.verified ? (
                    <span className="tag good">✓ Verified</span>
                  ) : (
                    <span className="tag muted">{job.status}</span>
                  )}
                  {job.cost_usd > 0 && (
                    <span className="tag muted">${job.cost_usd.toFixed(3)}</span>
                  )}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {hasNextPage && (
        <div className="mt-6 grid place-items-center gap-2">
          <button
            className="btn"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading…" : "Load more"}
          </button>
          <span className="muted small">
            Showing {jobs.length} of {totalCount}
          </span>
        </div>
      )}
    </div>
  );
}
