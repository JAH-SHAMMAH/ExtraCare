"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function TeachingStaffRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/modules/school/teachers");
  }, [router]);
  return null;
}
