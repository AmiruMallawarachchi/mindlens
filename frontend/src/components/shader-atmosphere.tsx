"use client";

import { useEffect, useRef } from "react";

export type Mood =
  | "neutral"
  | "calm"
  | "anxious"
  | "sad"
  | "angry"
  | "hopeful";

const PALETTES: Record<Mood, [number[], number[], number[]]> = {
  neutral: [
    [0.17, 0.28, 0.78],
    [0.49, 0.25, 0.94],
    [0.13, 0.75, 0.78],
  ],
  calm: [
    [0.04, 0.52, 0.69],
    [0.16, 0.33, 0.77],
    [0.23, 0.86, 0.69],
  ],
  anxious: [
    [0.29, 0.21, 0.68],
    [0.49, 0.37, 0.86],
    [0.20, 0.63, 0.77],
  ],
  sad: [
    [0.12, 0.20, 0.47],
    [0.30, 0.24, 0.60],
    [0.67, 0.30, 0.47],
  ],
  angry: [
    [0.88, 0.12, 0.10],
    [1.0, 0.32, 0.10],
    [0.70, 0.08, 0.25],
  ],
  hopeful: [
    [0.05, 0.63, 0.56],
    [0.18, 0.74, 0.84],
    [0.91, 0.48, 0.33],
  ],
};

const VERTEX_SHADER = `
  attribute vec2 a_position;
  void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;

  uniform vec2 u_resolution;
  uniform float u_time;
  uniform vec3 u_colorA;
  uniform vec3 u_colorB;
  uniform vec3 u_colorC;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
      mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
      f.y
    );
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 5; i++) {
      value += amplitude * noise(p);
      p = p * 2.03 + vec2(17.7, 9.2);
      amplitude *= 0.5;
    }
    return value;
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution.xy;
    uv.x *= u_resolution.x / u_resolution.y;
    float t = u_time * 0.075;

    vec2 q = vec2(
      fbm(uv * 1.35 + vec2(0.0, t)),
      fbm(uv * 1.35 + vec2(3.7, -t * 0.75))
    );
    vec2 r = vec2(
      fbm(uv * 1.65 + q * 1.6 + vec2(1.7, 9.2) + t * 0.7),
      fbm(uv * 1.65 + q * 1.4 + vec2(8.3, 2.8) - t * 0.55)
    );

    float field = fbm(uv * 1.15 + r * 1.9);
    float glowA = 1.0 - smoothstep(0.12, 0.78, distance(uv, vec2(0.22 + sin(t) * 0.07, 0.8)));
    float glowB = 1.0 - smoothstep(0.05, 0.95, distance(uv, vec2(1.2 + cos(t * 0.8) * 0.12, 0.18)));

    vec3 color = mix(u_colorA, u_colorB, smoothstep(0.18, 0.82, field));
    color = mix(color, u_colorC, clamp(glowA * 0.48 + glowB * 0.28, 0.0, 0.62));
    color *= 0.72 + field * 0.45;

    float vignette = smoothstep(1.35, 0.18, distance(uv, vec2(0.72, 0.5)));
    color *= 0.42 + vignette * 0.72;
    gl_FragColor = vec4(color, 1.0);
  }
`;

function compileShader(
  gl: WebGLRenderingContext,
  type: number,
  source: string,
) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

export function ShaderAtmosphere({
  mood,
  motionEnabled,
}: {
  mood: Mood;
  motionEnabled: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      powerPreference: "low-power",
    });
    if (!gl) return;

    const vertex = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
    const fragment = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    if (!vertex || !fragment) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );

    const position = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const resolution = gl.getUniformLocation(program, "u_resolution");
    const time = gl.getUniformLocation(program, "u_time");
    const colorA = gl.getUniformLocation(program, "u_colorA");
    const colorB = gl.getUniformLocation(program, "u_colorB");
    const colorC = gl.getUniformLocation(program, "u_colorC");
    const palette = PALETTES[mood];

    gl.uniform3fv(colorA, palette[0]);
    gl.uniform3fv(colorB, palette[1]);
    gl.uniform3fv(colorC, palette[2]);

    let frame = 0;
    const startedAt = performance.now();
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const render = (now: number) => {
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      const width = Math.max(1, Math.floor(canvas.clientWidth * ratio));
      const height = Math.max(1, Math.floor(canvas.clientHeight * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }

      const elapsed =
        motionEnabled && !reduceMotion ? (now - startedAt) / 1000 : 18;
      gl.uniform2f(resolution, width, height);
      gl.uniform1f(time, elapsed);
      gl.drawArrays(gl.TRIANGLES, 0, 6);

      if (motionEnabled && !reduceMotion) {
        frame = requestAnimationFrame(render);
      }
    };

    frame = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frame);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      gl.deleteBuffer(buffer);
    };
  }, [mood, motionEnabled]);

  return (
    <canvas
      ref={canvasRef}
      className="shader-atmosphere"
      aria-hidden="true"
    />
  );
}
