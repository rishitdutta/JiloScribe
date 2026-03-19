import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Check,
  Loader2,
  Mic,
  Pill,
  Square,
  Stethoscope,
  AlertCircle,
} from "lucide-react";

type ClinicalEntities = {
  patient: {
    name: string | null;
    age: string | null;
    sex: string | null;
    identifiers: string[] | null;
  } | null;
  encounter: {
    chief_complaint: string | null;
    reason_for_visit: string | null;
    encounter_type: string | null;
    notes: string | null;
  } | null;
  observations: {
    name: string;
    value: string | null;
    unit: string | null;
    interpretation: string | null;
    evidence: string[] | null;
  }[] | null;
  conditions: {
    name: string;
    status: string | null;
    severity: string | null;
    onset: string | null;
    evidence: string[] | null;
  }[] | null;
  medication_requests: {
    medication: string;
    dose: string | null;
    route: string | null;
    frequency: string | null;
    duration: string | null;
    indication: string | null;
    evidence: string[] | null;
  }[] | null;
};

type AppStage = "idle" | "recording" | "processing" | "results" | "error";
type OverlayStage = "recording" | "processing" | null;
type OverlayTransition = "clip" | "fade";

const BACKEND_HOST: string = "127.0.0.1";
const BACKEND_PORT: number = 8000;
const BASE_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const WS_URL = `ws://${BACKEND_HOST}:${BACKEND_PORT}`;
// const BASE_URL = '/api';
// const WS_URL = `ws://${window.location.host}/ws`;

function getBestMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  return candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

function mimeToExt(mime: string): string {
  if (mime.startsWith("audio/webm")) return "webm";
  if (mime.startsWith("audio/ogg")) return "ogg";
  if (mime.startsWith("audio/mp4")) return "mp4";
  return "bin";
}

async function pollPipelineJob(
  jobId: string,
  signal: AbortSignal,
  onStatus: (s: string) => void
): Promise<ClinicalEntities> {
  onStatus("Transcribing & diarizing…");
  while (!signal.aborted) {
    const res = await fetch(`${BASE_URL}/pipeline/${jobId}?wait=true`, { signal });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    const data = await res.json();
    if (data.status === "done" || data.status === "DONE") return data.result.entities as ClinicalEntities;
    if (data.status === "failed" || data.status === "FAILED") throw new Error(data.error ?? "Pipeline job failed");
    onStatus("Extracting clinical entities…");
    await new Promise((r) => setTimeout(r, 800));
  }
  throw new Error("Aborted");
}

export default function AmbientScribe() {
  const [appStage, setAppStage] = useState<AppStage>("idle");
  const [overlayStage, setOverlayStage] = useState<OverlayStage>(null);
  const [overlayTransition, setOverlayTransition] = useState<OverlayTransition>("clip");
  const [overlayVisible, setOverlayVisible] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [processingStatus, setProcessingStatus] = useState("Uploading recording…");
  const [fhirData, setFhirData] = useState<ClinicalEntities | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const timerRefs = useRef<number[]>([]);

  // Live caption refs (WebSocket + raw PCM)
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const finalTextRef = useRef("");
  const partialTextRef = useRef("");

  // Pipeline upload refs (MediaRecorder)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const clearAllTimers = () => {
    timerRefs.current.forEach((id) => window.clearTimeout(id));
    timerRefs.current = [];
  };

  const trackTimeout = (callback: () => void, delay: number) => {
    const id = window.setTimeout(callback, delay);
    timerRefs.current.push(id);
  };

  const showOverlay = (stage: Exclude<OverlayStage, null>) => {
    setOverlayTransition("clip");
    setOverlayStage(stage);
    setOverlayVisible(false);
    trackTimeout(() => setOverlayVisible(true), 20);
  };

  useEffect(() => {
    return () => {
      clearAllTimers();
      abortRef.current?.abort();
      wsRef.current?.close();
      audioContextRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // START RECORDING
  const startRecording = async () => {
    clearAllTimers();
    setTranscript("");
    setFhirData(null);
    setErrorMsg(null);
    finalTextRef.current = "";
    partialTextRef.current = "";
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // 1. WebSocket for live captions — raw Float32 PCM @ 16 kHz
      const ws = new WebSocket(`${WS_URL}/ws/live_caption`);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data as string);
        if (data.type === "final") {
          finalTextRef.current += data.text + " ";
          partialTextRef.current = "";
        }
        if (data.type === "partial") {
          partialTextRef.current = data.text;
        }
        setTranscript(finalTextRef.current + partialTextRef.current);
      };

      ws.onopen = () => console.log("[WS] connected");
      ws.onclose = () => console.log("[WS] closed");
      ws.onerror = (e) => console.error("[WS] error", e);

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(new Float32Array(input));
        }
      };

      // 2. MediaRecorder for pipeline upload — full audio blob
      const mimeType = getBestMimeType();
      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = mr;
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.start(250);

      setAppStage("recording");
      showOverlay("recording");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Microphone access denied");
      setAppStage("error");
    }
  };

  // STOP RECORDING
  const stopRecording = () => {
    clearAllTimers();

    // Tear down live-caption pipeline
    processorRef.current?.disconnect();
    audioContextRef.current?.close();
    wsRef.current?.close();

    setOverlayTransition("fade");
    setOverlayStage("processing");
    setOverlayVisible(true);
    setProcessingStatus("Uploading recording…");
    setAppStage("processing");

    const mr = mediaRecorderRef.current;
    if (!mr) return;

    mr.onstop = async () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());

      const mimeType = mr.mimeType || getBestMimeType();
      const ext = mimeToExt(mimeType);
      const blob = new Blob(chunksRef.current, { type: mimeType });
      chunksRef.current = [];

      const abort = new AbortController();
      abortRef.current = abort;

      try {
        const form = new FormData();
        form.append("file", blob, `recording.${ext}`);

        const createRes = await fetch(`${BASE_URL}/pipeline`, {
          method: "POST",
          body: form,
          signal: abort.signal,
        });

        if (!createRes.ok) {
          const text = await createRes.text();
          throw new Error(`Upload failed (${createRes.status}): ${text}`);
        }

        const { job_id } = await createRes.json();

        const result = await pollPipelineJob(job_id, abort.signal, setProcessingStatus);

        setFhirData(result);
        setAppStage("results");
        setOverlayVisible(false);
        trackTimeout(() => setOverlayStage(null), 500);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setErrorMsg(err instanceof Error ? err.message : "An unknown error occurred");
        setAppStage("error");
        setOverlayVisible(false);
        trackTimeout(() => setOverlayStage(null), 500);
      }
    };

    mr.stop();
  };

  const renderResults = () => {
    if (!fhirData) return null;
    return (
      <section className="space-y-4 pb-2">
        <div className="mb-1">
          <h2 className="text-xl font-semibold text-slate-900">JiloScribe AI</h2>
          <p className="text-sm text-slate-500">Clinical entities extracted for this encounter.</p>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
          <Check size={18} />
          <span className="text-sm font-semibold">Entities Extracted</span>
        </div>

        <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 sm:grid-cols-2">
          <p><span className="font-semibold text-slate-900">Patient:</span> {fhirData.patient?.name || "N/A"}</p>
          <p><span className="font-semibold text-slate-900">Chief Complaint:</span> {fhirData.encounter?.chief_complaint || "N/A"}</p>
          {fhirData.encounter?.reason_for_visit && (
            <p className="sm:col-span-2"><span className="font-semibold text-slate-900">Reason for Visit:</span> {fhirData.encounter.reason_for_visit}</p>
          )}
          {fhirData.encounter?.notes && (
            <p className="sm:col-span-2"><span className="font-semibold text-slate-900">Notes:</span> {fhirData.encounter.notes}</p>
          )}
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Stethoscope size={15} className="text-rose-500" /> Conditions (Dx)
          </h3>
          <ul className="space-y-2">
            {fhirData.conditions?.length ? fhirData.conditions.map((c, i) => (
              <li key={i} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium text-slate-800">{c.name}</span>
                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">{c.status || "unknown"}</span>
              </li>
            )) : <p className="text-xs text-slate-500">No conditions identified</p>}
          </ul>
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Activity size={15} className="text-cyan-600" /> Observations
          </h3>
          <ul className="space-y-2">
            {fhirData.observations?.length ? fhirData.observations.map((obs, i) => (
              <li key={i} className="flex flex-col rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium text-slate-800">{obs.name}</span>
                <span className="font-semibold text-cyan-700">{obs.value || "N/A"} {obs.unit || ""}</span>
                {obs.interpretation && <span className="text-xs text-slate-500">{obs.interpretation}</span>}
              </li>
            )) : <p className="text-xs text-slate-500">No observations recorded</p>}
          </ul>
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Pill size={15} className="text-amber-600" /> Medication Requests (Rx)
          </h3>
          <ul className="space-y-2">
            {fhirData.medication_requests?.length ? fhirData.medication_requests.map((med, i) => (
              <li key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <p className="font-medium text-slate-800">{med.medication}</p>
                <p className="text-xs text-slate-500">
                  {[med.dose, med.route, med.frequency, med.duration].filter(Boolean).join(" · ")}
                  {med.indication ? ` (${med.indication})` : ""}
                </p>
              </li>
            )) : <p className="text-xs text-slate-500">No medications prescribed</p>}
          </ul>
        </div>

        <button className="w-full rounded-xl bg-cyan-700 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800">
          Save to HMIS
        </button>
        <button
          onClick={() => { setAppStage("idle"); setTranscript(""); }}
          className="w-full rounded-xl border border-slate-200 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
        >
          New Encounter
        </button>
      </section>
    );
  };

  const clipPathClass =
    overlayTransition === "clip"
      ? overlayVisible
        ? "[clip-path:circle(145%_at_50%_calc(100%-5.5rem))]"
        : "[clip-path:circle(3.4rem_at_50%_calc(100%-5.5rem))]"
      : "[clip-path:circle(145%_at_50%_calc(100%-5.5rem))]";

  const overlayFadeClass =
    overlayTransition === "fade"
      ? overlayVisible
        ? "opacity-100 transition-opacity duration-500 ease-out"
        : "opacity-0 transition-opacity duration-500 ease-out"
      : "opacity-100";

  const clipTransitionClass =
    "transition-[clip-path] duration-680 ease-[cubic-bezier(0.22,1,0.36,1)]";

  return (
    <div className="relative mx-auto min-h-screen w-full max-w-md overflow-hidden border-x border-slate-200/70 bg-white/95 shadow-[0_20px_55px_-35px_rgba(21,58,95,0.5)]">
      <main className="relative min-h-screen px-5 pb-32 pt-14">
        {appStage === "results" ? (
          renderResults()
        ) : appStage === "error" ? (
          <section className="flex min-h-[60vh] flex-col items-center justify-center text-center gap-4">
            <div className="rounded-full bg-rose-50 p-4">
              <AlertCircle size={32} className="text-rose-500" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Something went wrong</h2>
              <p className="mt-1 text-sm text-slate-500 max-w-xs">{errorMsg}</p>
            </div>
            <button
              onClick={() => { setAppStage("idle"); setErrorMsg(null); }}
              className="rounded-xl bg-cyan-700 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-800"
            >
              Try Again
            </button>
          </section>
        ) : (
          <section className="flex min-h-[60vh] flex-col items-center justify-center text-center">
            <p className="mb-3 rounded-full bg-cyan-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-cyan-800">OPD Encounter</p>
            <h1 className="text-3xl font-semibold text-slate-900">JiloScribe AI</h1>
            <p className="mt-2 max-w-xs text-sm text-slate-500">Tap record to begin ambient transcription.</p>
          </section>
        )}
      </main>

      {overlayStage && (
        <div className={`pointer-events-none absolute inset-0 z-30 ${overlayFadeClass}`}>
          <div className="absolute inset-0 opacity-90 blur-[130px]">
            <div className={`overlay-gradient-motion absolute inset-0 bg-linear-to-b from-cyan-500 via-blue-700 to-indigo-800 ${clipTransitionClass} ${clipPathClass}`} />
          </div>
          <div className={`absolute inset-0 ${clipTransitionClass} ${clipPathClass}`}>
            <div className="overlay-gradient-motion absolute inset-0 bg-linear-to-b from-cyan-600 via-blue-700 to-indigo-800" />
            <div className="absolute -left-16 top-8 h-48 w-48 rounded-full bg-white/15 blur-3xl" />
            <div className="absolute -right-20 bottom-24 h-56 w-56 rounded-full bg-cyan-200/20 blur-3xl" />
            <div className="relative flex h-full flex-col px-5 pb-32 pt-14 text-white">
              {overlayStage === "recording" && (
                <>
                  <div className="mb-4 inline-flex w-fit items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-semibold">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-rose-300" />
                    Recording Live
                  </div>
                  <h2 className="mb-2 text-xl font-semibold">Live Transcript</h2>
                  <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-sm">
                    <p className="min-h-40 whitespace-pre-wrap text-sm leading-relaxed text-white/95">
                      {transcript || "Listening…"}
                    </p>
                  </div>
                </>
              )}
              {overlayStage === "processing" && (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <Loader2 className="mb-4 animate-spin" size={34} />
                  <p className="text-base font-semibold">Generating FHIR Resources…</p>
                  <p className="mt-2 text-sm text-cyan-100">{processingStatus}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2">
        {appStage === "processing" ? (
          <button disabled aria-label="Processing" className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-white text-cyan-700 shadow-xl shadow-cyan-900/20">
            <Loader2 size={30} className="animate-spin" />
          </button>
        ) : appStage === "recording" ? (
          <button onClick={stopRecording} aria-label="Stop recording" className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-rose-500 text-white shadow-xl shadow-rose-800/30 transition duration-300 hover:scale-105 hover:bg-rose-600">
            <Square size={30} />
          </button>
        ) : appStage === "results" ? null : (
          <button onClick={startRecording} aria-label="Start recording" className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-cyan-700 text-white shadow-xl shadow-cyan-800/30 transition duration-300 hover:scale-105 hover:bg-cyan-800">
            <Mic size={30} />
          </button>
        )}
      </div>
    </div>
  );
}