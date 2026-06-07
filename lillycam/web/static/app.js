"use strict";

// --- Dispense ---
const btnDispense = document.getElementById("btn-dispense");
const btnReverse = document.getElementById("btn-reverse");
const dispenseStatus = document.getElementById("dispense-status");

function setDispenseButtons(enabled) {
  btnDispense.disabled = !enabled;
  btnReverse.disabled = !enabled;
}

btnDispense.addEventListener("click", async () => {
  setDispenseButtons(false);
  dispenseStatus.textContent = "Dispensing...";
  try {
    const res = await fetch("/dispense", { method: "POST" });
    dispenseStatus.textContent = res.ok ? "Done!" : "Error";
  } catch {
    dispenseStatus.textContent = "Network error";
  }
  setDispenseButtons(true);
  setTimeout(() => { dispenseStatus.textContent = ""; }, 3000);
});

btnReverse.addEventListener("click", async () => {
  setDispenseButtons(false);
  dispenseStatus.textContent = "Reversing...";
  try {
    const res = await fetch("/reverse", { method: "POST" });
    dispenseStatus.textContent = res.ok ? "Done!" : "Error";
  } catch {
    dispenseStatus.textContent = "Network error";
  }
  setDispenseButtons(true);
  setTimeout(() => { dispenseStatus.textContent = ""; }, 3000);
});

// --- Servo ---
const slider = document.getElementById("servo-slider");
const angleLabel = document.getElementById("servo-angle-label");

// Sync slider position from server on page load so reconnecting never causes a jump
fetch("/servo")
  .then(r => r.json())
  .then(data => {
    slider.value = data.angle;
    angleLabel.textContent = data.angle + "\u00b0";
  })
  .catch(() => {});

// Update label live while dragging, but don't move servo yet
slider.addEventListener("input", () => {
  angleLabel.textContent = slider.value + "\u00b0";
});

// Send to servo only on release (invert: slider right = servo right physically)
slider.addEventListener("change", () => {
  sendAngle(180 - slider.value);
});

async function sendAngle(angle) {
  await fetch("/rotate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ angle: Number(angle) }),
  });
}

// --- Push-to-Talk ---
// Note: getUserMedia requires HTTPS (or localhost). Enable Tailscale HTTPS
// certificates (see docs/pi-setup.md) — plain HTTP will show "Mic error".
const pttBtn = document.getElementById("btn-ptt");
const pttStatus = document.getElementById("ptt-status");
let mediaStream = null;
let audioCtx = null;
let audioSource = null;
let processor = null;
let pcmChunks = [];

pttBtn.addEventListener("mousedown", startRecording);
pttBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); });
pttBtn.addEventListener("mouseup", stopAndSend);
pttBtn.addEventListener("touchend", stopAndSend);

async function startRecording() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new AudioContext();
    audioSource = audioCtx.createMediaStreamSource(mediaStream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    pcmChunks = [];
    processor.onaudioprocess = (e) => {
      pcmChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    audioSource.connect(processor);
    processor.connect(audioCtx.destination);
    pttBtn.classList.add("active");
    pttStatus.textContent = "Recording...";
  } catch {
    pttStatus.textContent = "Mic error: HTTPS required";
    setTimeout(() => { pttStatus.textContent = ""; }, 4000);
  }
}

function stopAndSend() {
  if (!audioCtx) return;
  processor.disconnect();
  audioSource.disconnect();
  mediaStream.getTracks().forEach((t) => t.stop());
  pttBtn.classList.remove("active");
  pttStatus.textContent = "Sending...";

  const sampleRate = audioCtx.sampleRate;
  audioCtx.close();
  audioCtx = null;

  const totalLen = pcmChunks.reduce((s, c) => s + c.length, 0);
  const pcm = new Float32Array(totalLen);
  let off = 0;
  for (const chunk of pcmChunks) { pcm.set(chunk, off); off += chunk.length; }

  sendAudio(encodeWAV(pcm, sampleRate));
}

// Encode Float32 mono PCM as a 16-bit mono WAV ArrayBuffer.
function encodeWAV(pcm, sampleRate) {
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const v = new DataView(buf);
  const str = (off, s) => [...s].forEach((c, i) => v.setUint8(off + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true);
  str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buf;
}

async function sendAudio(wavBuffer) {
  try {
    const res = await fetch("/speak", {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: wavBuffer,
    });
    pttStatus.textContent = res.ok ? "Sent" : "Error";
  } catch {
    pttStatus.textContent = "Network error";
  }
  setTimeout(() => { pttStatus.textContent = ""; }, 3000);
}

// --- Capture Still ---
document.getElementById("btn-capture").addEventListener("click", async () => {
  const status = document.getElementById("capture-status");
  status.textContent = "Capturing...";
  try {
    const res = await fetch("/capture", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      const filename = data.path.split("/").pop();
      status.innerHTML = `Saved: <a href="/captures/${encodeURIComponent(filename)}" target="_blank">${filename}</a>`;
    } else {
      status.textContent = "Error";
    }
  } catch {
    status.textContent = "Network error";
  }
});
