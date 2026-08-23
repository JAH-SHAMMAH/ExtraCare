"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Loader2, ChevronLeft, ChevronRight, Clock, CheckCircle, AlertCircle,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { cbtApi } from "@/lib/api";
import type { CBTExam } from "@/types";

interface Question {
  id: string;
  question_text: string;
  question_type: string;
  options?: string[];
  correct_answer?: string;
  points?: number;
}

interface Attempt {
  id: string;
  exam_id: string;
  student_id: string;
  status: string;
  started_at: string;
  submitted_at: string | null;
}

export default function TakeExamPage() {
  const router = useRouter();
  const params = useParams();
  const examId = params.exam_id as string;

  // Loading states
  const [isLoadingExam, setIsLoadingExam] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);

  // Data
  const [exam, setExam] = useState<CBTExam | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);

  // UI state
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load exam and questions
  useEffect(() => {
    const loadExam = async () => {
      try {
        const examData = await cbtApi.exams.get(examId);
        setExam(examData);

        // Load questions (without answers for student)
        const questionsData = await cbtApi.questions.list(examId, false);
        setQuestions(questionsData.items || questionsData || []);
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Failed to load exam.");
        toast.error("Failed to load exam.");
      } finally {
        setIsLoadingExam(false);
      }
    };

    loadExam();
  }, [examId]);

  // Start attempt
  const startAttempt = useCallback(async () => {
    setIsStarting(true);
    try {
      const attemptData = await cbtApi.attempts.start(examId, "");
      setAttempt(attemptData);

      // Initialize timer if exam has duration
      if (attemptData.started_at && exam?.duration_minutes) {
        const startTime = new Date(attemptData.started_at).getTime();
        const now = Date.now();
        const elapsedSeconds = Math.floor((now - startTime) / 1000);
        const remainingSeconds = (exam.duration_minutes * 60) - elapsedSeconds;
        setTimeRemaining(Math.max(0, remainingSeconds));
      }
    } catch (err: any) {
      const message = err?.response?.data?.detail || "Failed to start exam.";
      setError(message);
      toast.error(message);
    } finally {
      setIsStarting(false);
    }
  }, [examId, exam?.duration_minutes]);

  // Timer countdown
  useEffect(() => {
    if (!attempt || !exam?.duration_minutes || timeRemaining === null) return;

    if (timeRemaining <= 0) {
      toast.error("Time's up! Submitting your exam...");
      // Auto-submit
      return;
    }

    const timer = setInterval(() => {
      setTimeRemaining((prev) => (prev !== null ? prev - 1 : null));
    }, 1000);

    return () => clearInterval(timer);
  }, [attempt, exam?.duration_minutes, timeRemaining]);

  // Submit attempt
  const submitExam = useCallback(async () => {
    if (!attempt) return;

    setIsSubmitting(true);
    try {
      const submissionAnswers = questions.map((q) => ({
        question_id: q.id,
        answer_text: answers[q.id] || "",
      }));

      await cbtApi.attempts.submit(attempt.id, submissionAnswers);
      setIsCompleted(true);
      toast.success("Exam submitted successfully.");
    } catch (err: any) {
      const message = err?.response?.data?.detail || "Failed to submit exam.";
      setError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [attempt, questions, answers]);

  // Format time as MM:SS
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const currentQuestion = questions[currentQuestionIndex];
  const isFirstQuestion = currentQuestionIndex === 0;
  const isLastQuestion = currentQuestionIndex === questions.length - 1;
  const isTimeUp = timeRemaining === 0;

  // UI: Loading
  if (isLoadingExam) {
    return (
      <div className="p-8 max-w-4xl mx-auto flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
      </div>
    );
  }

  // UI: Exam not found or load error
  if (!exam || questions.length === 0) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-amber-600" />
          <h2 className="text-lg font-bold text-slate-900 mb-2">Could not load exam</h2>
          <p className="text-slate-500 text-sm mb-4">{error || "Please try again."}</p>
          <Link href="/dashboard/my-exams" className="text-brand-600 hover:underline text-sm font-semibold">
            Back to My Exams
          </Link>
        </div>
      </div>
    );
  }

  // UI: Completed
  if (isCompleted) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <CheckCircle className="w-16 h-16 mx-auto mb-4 text-emerald-600" />
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Exam Submitted</h2>
          <p className="text-slate-500 text-sm mb-4">
            Your exam has been submitted successfully. Your results will be available once your teacher publishes them.
          </p>
          <Link href="/dashboard/my-exams" className="inline-block bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
            Back to My Exams
          </Link>
        </div>
      </div>
    );
  }

  // UI: Not started
  if (!attempt) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-8">
          <h1 className="text-2xl font-bold text-slate-900 mb-2">{exam.title}</h1>
          {exam.description && <p className="text-slate-600 text-sm mb-4">{exam.description}</p>}

          <div className="space-y-3 mb-6">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <span className="font-semibold">{questions.length} questions</span>
            </div>
            {exam.duration_minutes && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Clock size={16} />
                <span className="font-semibold">{exam.duration_minutes} minutes</span>
              </div>
            )}
            {exam.pass_percentage && (
              <div className="text-sm text-slate-600">
                <span className="font-semibold">Pass: {exam.pass_percentage}%</span>
              </div>
            )}
          </div>

          <button
            onClick={startAttempt}
            disabled={isStarting}
            className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-semibold py-2 rounded-lg transition"
          >
            {isStarting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : "Start Exam"}
          </button>

          <Link href="/dashboard/my-exams" className="block text-center text-brand-600 hover:underline text-sm font-semibold mt-4">
            Back to My Exams
          </Link>
        </div>
      </div>
    );
  }

  // UI: In-progress
  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header with timer */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{exam.title}</h1>
        {exam.duration_minutes && (
          <div className={cn(
            "text-lg font-bold px-3 py-1 rounded-lg flex items-center gap-2",
            timeRemaining && timeRemaining <= 60
              ? "bg-red-100 text-red-700"
              : "bg-slate-100 text-slate-700",
          )}>
            <Clock size={16} />
            {formatTime(timeRemaining ?? 0)}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-600">
            Question {currentQuestionIndex + 1} of {questions.length}
          </span>
          <span className="text-xs text-slate-500">
            {Object.keys(answers).length} answered
          </span>
        </div>
        <div className="w-full bg-slate-200 rounded-full h-2">
          <div
            className="bg-brand-600 h-2 rounded-full transition-all"
            style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Question card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">
          {currentQuestion.question_text}
        </h2>

        {/* Options */}
        {currentQuestion.question_type === "MCQ" && currentQuestion.options && (
          <div className="space-y-2">
            {currentQuestion.options.map((option, idx) => (
              <label key={idx} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                <input
                  type="radio"
                  name={`question-${currentQuestion.id}`}
                  value={option}
                  checked={answers[currentQuestion.id] === option}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [currentQuestion.id]: e.target.value }))}
                  className="w-4 h-4"
                />
                <span className="text-sm text-slate-700">{option}</span>
              </label>
            ))}
          </div>
        )}

        {/* True/False */}
        {currentQuestion.question_type === "TRUE_FALSE" && (
          <div className="space-y-2">
            {["True", "False"].map((option) => (
              <label key={option} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                <input
                  type="radio"
                  name={`question-${currentQuestion.id}`}
                  value={option.toLowerCase()}
                  checked={answers[currentQuestion.id] === option.toLowerCase()}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [currentQuestion.id]: e.target.value }))}
                  className="w-4 h-4"
                />
                <span className="text-sm text-slate-700">{option}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Navigation and submit */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
          disabled={isFirstQuestion}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-semibold text-slate-700"
        >
          <ChevronLeft size={16} />
          Previous
        </button>

        <div className="flex gap-1">
          {questions.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentQuestionIndex(idx)}
              className={cn(
                "w-2 h-2 rounded-full transition",
                idx === currentQuestionIndex
                  ? "bg-brand-600"
                  : answers[questions[idx].id]
                    ? "bg-emerald-500"
                    : "bg-slate-300",
              )}
            />
          ))}
        </div>

        {isLastQuestion ? (
          <button
            onClick={submitExam}
            disabled={isSubmitting || isTimeUp}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-sm font-semibold"
          >
            {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
            Submit Exam
          </button>
        ) : (
          <button
            onClick={() => setCurrentQuestionIndex((prev) => Math.min(questions.length - 1, prev + 1))}
            disabled={isLastQuestion}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-semibold text-slate-700"
          >
            Next
            <ChevronRight size={16} />
          </button>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
    </div>
  );
}
