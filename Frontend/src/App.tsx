import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Check,
  Loader2,
  Mic,
  Pill,
  Square,
  Stethoscope,
} from "lucide-react";

type Observation = {
  resourceType: "Observation";
  code: string;
  value: string;
};

type Condition = {
  resourceType: "Condition";
  code: string;
  clinicalStatus: string;
};

type MedicationRequest = {
  resourceType: "MedicationRequest";
  drug: string;
  dosage: string;
};

type FhirData = {
  patientId: string;
  encounter: string;
  observations: Observation[];
  conditions: Condition[];
  medications: MedicationRequest[];
};

type AppStage = "idle" | "recording" | "processing" | "results";
type OverlayStage = "recording" | "processing" | null;
type OverlayTransition = "clip" | "fade";

export default function AmbientScribe() {
  const [appStage, setAppStage] = useState<AppStage>("idle");
  const [overlayStage, setOverlayStage] = useState<OverlayStage>(null);
  const [overlayTransition, setOverlayTransition] =
    useState<OverlayTransition>("clip");
  const [overlayVisible, setOverlayVisible] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [fhirData, setFhirData] = useState<FhirData | null>(null);

  const timerRefs = useRef<number[]>([]);

  const clearAllTimers = () => {
    timerRefs.current.forEach((timerId) => window.clearTimeout(timerId));
    timerRefs.current = [];
  };

  const trackTimeout = (callback: () => void, delay: number) => {
    const timeoutId = window.setTimeout(callback, delay);
    timerRefs.current.push(timeoutId);
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
    };
  }, []);

  const startRecording = () => {
    clearAllTimers();
    setTranscript("");
    setFhirData(null);
    setAppStage("recording");
    showOverlay("recording");

    const chunks = [
      { text: "Patient complain kar raha hai... ", delay: 900 },
      { text: "severe headache since 2 days. ", delay: 2200 },
      { text: "Blood pressure check kiya, it is 150/95. ", delay: 3500 },
      {
        text: "Prescribing Paracetamol 500mg SOS and Telmisartan 40mg daily.",
        delay: 5000,
      },
    ];

    chunks.forEach((chunk) => {
      trackTimeout(() => {
        setTranscript((prev) => prev + chunk.text);
      }, chunk.delay);
    });
  };

  const stopRecording = () => {
    clearAllTimers();
    setAppStage("processing");
    setOverlayTransition("fade");
    setOverlayStage("processing");
    setOverlayVisible(true);

    trackTimeout(() => {
      setFhirData({
        patientId: "PT-98765",
        encounter: "ENC-20260317",
        observations: [
          {
            resourceType: "Observation",
            code: "Blood Pressure",
            value: "150/95 mmHg",
          },
        ],
        conditions: [
          {
            resourceType: "Condition",
            code: "Severe Headache",
            clinicalStatus: "active",
          },
        ],
        medications: [
          {
            resourceType: "MedicationRequest",
            drug: "Paracetamol",
            dosage: "500mg SOS",
          },
          {
            resourceType: "MedicationRequest",
            drug: "Telmisartan",
            dosage: "40mg daily",
          },
        ],
      });

      setAppStage("results");
      setOverlayVisible(false);
      trackTimeout(() => {
        setOverlayStage(null);
      }, 520);
    }, 1800);
  };

  const renderResults = () => {
    if (!fhirData) {
      return null;
    }

    return (
      <section className="space-y-4 pb-2">
        <div className="mb-1">
          <h2 className="text-xl font-semibold text-slate-900">
            JiloScribe AI
          </h2>
          <p className="text-sm text-slate-500">
            FHIR summary generated for this encounter.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
          <Check size={18} />
          <span className="text-sm font-semibold">
            FHIR Resources Generated
          </span>
        </div>

        <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 sm:grid-cols-2">
          <p>
            <span className="font-semibold text-slate-900">Patient:</span>{" "}
            {fhirData.patientId}
          </p>
          <p>
            <span className="font-semibold text-slate-900">Encounter:</span>{" "}
            {fhirData.encounter}
          </p>
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Stethoscope size={15} className="text-rose-500" />
            Conditions (Dx)
          </h3>
          <ul className="space-y-2">
            {fhirData.conditions.map((condition) => (
              <li
                key={condition.code}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
              >
                <span className="font-medium text-slate-800">
                  {condition.code}
                </span>
                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">
                  {condition.clinicalStatus}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Activity size={15} className="text-cyan-600" />
            Observations (Vitals)
          </h3>
          <ul className="space-y-2">
            {fhirData.observations.map((observation) => (
              <li
                key={observation.code}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
              >
                <span className="font-medium text-slate-800">
                  {observation.code}
                </span>
                <span className="font-semibold text-cyan-700">
                  {observation.value}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Pill size={15} className="text-amber-600" />
            Medication Requests (Rx)
          </h3>
          <ul className="space-y-2">
            {fhirData.medications.map((medication) => (
              <li
                key={medication.drug}
                className="rounded-lg bg-slate-50 px-3 py-2 text-sm"
              >
                <p className="font-medium text-slate-800">{medication.drug}</p>
                <p className="text-xs text-slate-500">{medication.dosage}</p>
              </li>
            ))}
          </ul>
        </div>

        <button className="w-full rounded-xl bg-cyan-700 py-3 text-sm font-semibold text-white transition hover:bg-cyan-800">
          Save to HMIS
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
        ) : (
          <section className="flex min-h-[60vh] flex-col items-center justify-center text-center">
            <p className="mb-3 rounded-full bg-cyan-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-cyan-800">
              OPD Encounter
            </p>
            <h1 className="text-3xl font-semibold text-slate-900">
              JiloScribe AI
            </h1>
            <p className="mt-2 max-w-xs text-sm text-slate-500">
              Tap record to begin ambient transcription.
            </p>
          </section>
        )}
      </main>

      {overlayStage && (
        <div
          className={`pointer-events-none absolute inset-0 z-30 ${overlayFadeClass}`}
        >
          <div className="absolute inset-0 opacity-90 blur-[130px]">
            <div
              className={`overlay-gradient-motion absolute inset-0 bg-linear-to-b from-cyan-500 via-blue-700 to-indigo-800 ${clipTransitionClass} ${clipPathClass}`}
            />
          </div>

          <div
            className={`absolute inset-0 ${clipTransitionClass} ${clipPathClass}`}
          >
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

                  <h2 className="mb-2 text-xl font-semibold">
                    Live Transcript
                  </h2>
                  <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-sm">
                    <p className="min-h-40 whitespace-pre-wrap text-sm leading-relaxed text-white/95">
                      {transcript || "Listening..."}
                    </p>
                  </div>
                </>
              )}

              {overlayStage === "processing" && (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <Loader2 className="mb-4 animate-spin" size={34} />
                  <p className="text-base font-semibold">
                    Generating FHIR Resources...
                  </p>
                  <p className="mt-2 text-sm text-cyan-100">
                    Structuring observations, conditions, and prescriptions.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2">
        {appStage === "processing" ? (
          <button
            disabled
            aria-label="Generating FHIR"
            title="Generating FHIR"
            className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-white text-cyan-700 shadow-xl shadow-cyan-900/20"
          >
            <Loader2 size={30} className="animate-spin" />
          </button>
        ) : appStage === "recording" ? (
          <button
            onClick={stopRecording}
            aria-label="Stop recording"
            title="Stop recording"
            className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-rose-500 text-white shadow-xl shadow-rose-800/30 transition duration-300 hover:scale-105 hover:bg-rose-600"
          >
            <Square size={30} />
          </button>
        ) : (
          <button
            onClick={startRecording}
            aria-label="Start recording"
            title="Start recording"
            className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-cyan-700 text-white shadow-xl shadow-cyan-800/30 transition duration-300 hover:scale-105 hover:bg-cyan-800"
          >
            <Mic size={30} />
          </button>
        )}
      </div>
    </div>
  );
}
