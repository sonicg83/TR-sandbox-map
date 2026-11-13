export function worldToScreen(x, y, v) {
  return {x:v.width/2+(x-v.cx-(y-v.cy))*32*v.scale, y:v.height/2-(x-v.cx+y-v.cy)*16*v.scale};
}
export function screenToWorld(px, py, v) {
  const a=(px-v.width/2)/(32*v.scale), b=-(py-v.height/2)/(16*v.scale);
  return {x:Math.round(v.cx+(a+b)/2),y:Math.round(v.cy+(b-a)/2)};
}
