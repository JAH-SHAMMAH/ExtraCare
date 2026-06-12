"use client";

import { useSchoolPersona, type SchoolPersona } from "@/hooks/useSchoolPersona";
import { useAuthStore } from "@/lib/store";
import { useSchoolContext } from "@/hooks/useSchoolExperience";
import { Link2Off } from "lucide-react";
import { AssignmentsWidget } from "./AssignmentsWidget";
import { CBTWidget } from "./CBTWidget";
import { BehaviourWidget } from "./BehaviourWidget";
import { FeedbackWidget } from "./FeedbackWidget";
import { TuckshopWidget } from "./TuckshopWidget";
import { ClubsWidget } from "./ClubsWidget";
import { JournalsWidget } from "./JournalsWidget";
import { RemarksWidget } from "./RemarksWidget";

/**
 * Renders the school-experience widget grid tailored to the user's persona.
 * Only mounts when the school module is enabled (caller is responsible).
 *
 * Persona widget mix:
 *   admin    → school-wide oversight: feedback queue, behaviour, tuckshop ops, clubs
 *   teacher  → daily classroom focus: assignments, CBT, behaviour, remarks, journals
 *   student  → personal slice: my assignments, my exams, my remarks, my feedback
 */
export function SchoolWidgets() {
  const persona = useSchoolPersona();
  const { user } = useAuthStore();
  const { data: ctx } = useSchoolContext();
  if (!user) return null;

  const widgets = WIDGETS_BY_PERSONA[persona];

  // Non-admin personas rely on /me/school-context to resolve a Student or
  // teacher-of record. If neither resolves, every for_me widget will return
  // empty — so surface that explicitly with a next step instead of showing
  // six "no data" cards.
  const needsLink = persona !== "admin" && ctx && !ctx.student && !ctx.is_teacher;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-black text-slate-900">School Experience</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {PERSONA_TAGLINE[persona]}
          </p>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 bg-slate-100 px-2 py-1 rounded">
          {persona} view
        </span>
      </div>

      {needsLink && <UnlinkedBanner email={user.email} />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {widgets.map((W, i) => (
          <W key={i} />
        ))}
      </div>
    </div>
  );
}

function UnlinkedBanner({ email }: { email?: string }) {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
      <Link2Off size={18} className="text-amber-600 shrink-0 mt-0.5" />
      <div className="flex-1 text-sm">
        <p className="font-semibold text-amber-900">Your account isn't linked to a student or teacher record yet.</p>
        <p className="text-amber-800 mt-1">
          Personalised widgets stay empty until your school admin links{email ? ` ${email}` : " your email"} to a Student profile or assigns you to a class/subject.
        </p>
        <a
          href="/dashboard/modules/school/students"
          className="inline-block mt-2 text-amber-900 underline font-medium hover:text-amber-700"
        >
          Open the student directory →
        </a>
      </div>
    </div>
  );
}

const PERSONA_TAGLINE: Record<SchoolPersona, string> = {
  admin: "School-wide pulse across every module.",
  teacher: "Today's classroom signals, in one place.",
  student: "Your assignments, exams, and feedback at a glance.",
};

const WIDGETS_BY_PERSONA: Record<SchoolPersona, Array<() => React.ReactElement | null>> = {
  admin: [
    () => <FeedbackWidget audience="admin" />,
    () => <BehaviourWidget audience="admin" />,
    () => <TuckshopWidget />,
    () => <CBTWidget audience="admin" />,
    () => <ClubsWidget />,
    () => <JournalsWidget />,
  ],
  teacher: [
    () => <AssignmentsWidget audience="teacher" />,
    () => <CBTWidget audience="teacher" />,
    () => <BehaviourWidget audience="teacher" />,
    () => <RemarksWidget audience="teacher" />,
    () => <ClubsWidget />,
    () => <JournalsWidget />,
  ],
  student: [
    () => <AssignmentsWidget audience="student" />,
    () => <CBTWidget audience="student" />,
    () => <RemarksWidget audience="student" />,
    () => <FeedbackWidget audience="student" />,
    () => <ClubsWidget />,
    () => <JournalsWidget />,
  ],
};
