const levels = [.1, .5, 1];

export function nextZoom(current, direction) {
  if (direction > 0) return levels.find(value => value > current + 1e-9) ?? levels.at(-1);
  return [...levels].reverse().find(value => value < current - 1e-9) ?? levels[0];
}

export function zoomAt(view, scale, point) {
  const dx = point.x - view.width / 2;
  const dy = point.y - view.height / 2;
  const difference = 1 / view.scale - 1 / scale;
  const a = dx / 32 * difference, b = -dy / 16 * difference;
  return {...view, cx:view.cx + (a + b) / 2, cy:view.cy + (b - a) / 2, scale};
}
