// Browser capture stays local until the user explicitly submits the resulting WAV.
export function encodeWav(buffer, maxSeconds = Infinity) {
  const frames = Math.min(buffer.length, Math.floor(maxSeconds * buffer.sampleRate));
  const bytes = new ArrayBuffer(44 + frames * 2), view = new DataView(bytes);
  const text = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, 36 + frames * 2, true); text(8, 'WAVE'); text(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, frames * 2, true);
  const channels = Array.from({length: buffer.numberOfChannels}, (_, i) => buffer.getChannelData(i));
  for (let i = 0; i < frames; i++) {
    const sample = Math.max(-1, Math.min(1, channels.reduce((sum, c) => sum + c[i], 0) / channels.length));
    view.setInt16(44 + i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  return new Blob([bytes], {type: 'audio/wav'});
}

export class SentenceRecorder {
  constructor(onState, onReady) { this.onState = onState; this.onReady = onReady; this.token = 0; this.phase = 'idle'; }
  get active() { return ['requesting', 'recording', 'encoding'].includes(this.phase); }
  status(phase, error = '') { this.phase = phase; this.onState({phase, error}); }
  release() { clearInterval(this.timer); this.stream?.getTracks().forEach(t => t.stop()); this.stream = null; }
  cancel() {
    this.token++; const recorder = this.recorder; this.recorder = null;
    if (recorder?.state !== 'inactive' && recorder) recorder.stop();
    this.release(); this.status('idle');
  }
  stop() { if (this.recorder?.state === 'recording') { this.status('encoding'); this.recorder.stop(); this.release(); } }
  async start(scope, maxSeconds) {
    if (this.active) return;
    if (!globalThis.isSecureContext || !navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder) {
      this.status('error', '当前浏览器无法录音。请通过 localhost 或 HTTPS 打开，并使用支持录音的浏览器；也可以上传音频。'); return;
    }
    const token = ++this.token; this.status('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}, video: false});
      if (token !== this.token) { stream.getTracks().forEach(t => t.stop()); return; }
      this.stream = stream;
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(t => MediaRecorder.isTypeSupported(t));
      const recorder = this.recorder = new MediaRecorder(stream, mimeType ? {mimeType} : {}), chunks = [];
      recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      recorder.onerror = () => { if (token === this.token) { this.cancel(); this.status('error', '录音设备中断，请重新录制或上传音频。'); } };
      recorder.onstop = async () => {
        if (token !== this.token) return;
        this.release(); this.status('encoding'); let audio;
        try {
          audio = new (globalThis.AudioContext || globalThis.webkitAudioContext)();
          const buffer = await audio.decodeAudioData(await new Blob(chunks, {type: recorder.mimeType}).arrayBuffer());
          if (token !== this.token) return;
          if (buffer.duration < .2) throw new Error('录音太短，请重新录制。');
          const file = new File([encodeWav(buffer, maxSeconds)], `补录-${scope.blockId}.wav`, {type: 'audio/wav'});
          this.recorder = null; this.phase = 'idle'; this.onReady(scope, file); this.status('idle');
        } catch (error) { if (token === this.token) this.status('error', error.message.includes('录音太短') ? error.message : '录音转换失败，请重录或上传WAV音频。'); }
        finally { await audio?.close(); }
      };
      recorder.start(100); this.started = performance.now(); this.status('recording');
      this.timer = setInterval(() => {
        const elapsed = (performance.now() - this.started) / 1000;
        this.onState({phase: 'recording', seconds: Math.min(elapsed, maxSeconds)});
        if (elapsed >= maxSeconds) this.stop();
      }, 100);
    } catch (error) {
      if (token !== this.token) return;
      this.release(); this.status('error', error.name === 'NotAllowedError' ? '麦克风权限未开启。请在地址栏的网站权限中允许麦克风，或选择上传音频。' : error.name === 'NotFoundError' ? '没有找到麦克风，请连接设备或上传音频。' : '麦克风不可用，请检查设备是否被占用，或上传音频。');
    }
  }
}
