// ScoreDial — SVG progress ring showing a score from the API (0–100).
export default function ScoreDial({ score = 0, size = 80, tone = '#8F4100' }) {
  const r = 38;
  const circ = 2 * Math.PI * r; // ≈ 238.8 for size 80
  const norm = Math.max(0, Math.min(100, Number(score) || 0));
  const offset = circ * (1 - norm / 100);
  return (
    <div className="score" style={{ width: size, height: size }}>
      <svg viewBox="0 0 80 80" width={size} height={size}>
        <circle className="strack" cx="40" cy="40" r={r} />
        <circle
          className="sbar"
          cx="40"
          cy="40"
          r={r}
          style={{ stroke: tone, strokeDashoffset: offset, strokeDasharray: circ }}
        />
      </svg>
      <div className="scorenum">
        <span className="n">{Math.round(norm)}</span>
        <i>/100</i>
      </div>
    </div>
  );
}