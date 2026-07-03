// Geometry for the "living rings" activity mark (design/overlay-ux.md §4): a circle whose
// radius is modulated by a sine wave. The path is static; the CSS spins it, which makes the
// waves travel around the ring, and the gradient stroked along it flows with them.

/** SVG path for a closed wavy ring: `radius ± amplitude` over `waves` periods, centered at
 *  (`center`, `center`), sampled as a fine polyline (2° steps at the default 180 samples). */
export function wavyRingPath(
  center: number,
  radius: number,
  amplitude: number,
  waves: number,
  phase: number,
  samples = 180,
): string {
  const steps = Array.from({ length: samples }, (_, index) => {
    const theta = (index / samples) * 2 * Math.PI;
    const r = radius + amplitude * Math.sin(waves * theta + phase);
    const x = center + r * Math.cos(theta);
    const y = center + r * Math.sin(theta);
    return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  });
  return `${steps.join(" ")} Z`;
}
