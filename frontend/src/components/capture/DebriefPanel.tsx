"use client";

import { useEffect, useState } from "react";
import { answerQuestion, requestDebrief } from "@/services/api";

interface Question {
  question_id: string;
  question_type: string;
  question_text: string;
  answer_text?: string | null;
}

export default function DebriefPanel({
  sessionId,
  onGenerate,
}: {
  sessionId: string;
  onGenerate: () => void;
}) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let active = true;
    void requestDebrief(sessionId).then((res) => {
      if (!active) return;
      const qs: Question[] = res.questions ?? [];
      setQuestions(qs);
      const saved: Record<string, string> = {};
      const done: Record<string, boolean> = {};
      for (const q of qs) {
        if (q.answer_text) {
          saved[q.question_id] = q.answer_text;
          done[q.question_id] = true;
        }
      }
      setAnswers(saved);
      setSubmitted(done);
    });
    return () => {
      active = false;
    };
  }, [sessionId]);

  const submit = async (q: Question) => {
    const text = answers[q.question_id];
    if (!text) return;
    await answerQuestion(sessionId, q.question_id, text);
    setSubmitted((s) => ({ ...s, [q.question_id]: true }));
  };

  const allDone = questions.length > 0 && questions.every((q) => submitted[q.question_id]);

  return (
    <div className="mt-6 rounded-2xl border bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Debrief</h2>
      <p className="mt-1 text-sm text-slate-500">
        Answer a few follow-ups so the Work Map captures your reasoning and guardrails.
      </p>
      <div className="mt-4 space-y-4">
        {questions.map((q) => (
          <div key={q.question_id} className="rounded-lg border p-3">
            <p className="text-xs uppercase text-slate-500">{q.question_type}</p>
            <p className="mt-1 text-sm font-medium">{q.question_text}</p>
            <textarea
              rows={2}
              value={answers[q.question_id] ?? ""}
              onChange={(e) => setAnswers((a) => ({ ...a, [q.question_id]: e.target.value }))}
              className="mt-2 w-full rounded border px-2 py-1 text-sm"
              placeholder="Your answer"
              disabled={submitted[q.question_id]}
            />
            <button
              onClick={() => submit(q)}
              disabled={submitted[q.question_id]}
              className="mt-2 rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {submitted[q.question_id] ? "Saved" : "Save answer"}
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={onGenerate}
        disabled={!allDone}
        className="mt-4 rounded-lg bg-emerald-700 px-4 py-2 text-white disabled:opacity-50"
      >
        Generate Work Map
      </button>
    </div>
  );
}
