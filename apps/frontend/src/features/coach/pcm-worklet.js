// Worklet de captura del coach de voz (MVP-02 REQ-06), con el patrón de pcm-worklet.js de
// CareerAI: junta los bloques de 128 muestras del micrófono y manda copias de ~20 ms al hilo
// principal, que remuestrea a 16 kHz y arma los frames (audio.ts).
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.size = Math.max(128, Math.round(sampleRate / 50)); // ~20 ms a la frecuencia real
    this.buffer = new Float32Array(this.size);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) {
      let offset = 0;
      while (offset < channel.length) {
        const take = Math.min(channel.length - offset, this.size - this.filled);
        this.buffer.set(channel.subarray(offset, offset + take), this.filled);
        this.filled += take;
        offset += take;
        if (this.filled === this.size) {
          this.port.postMessage(this.buffer.slice(0));
          this.filled = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
