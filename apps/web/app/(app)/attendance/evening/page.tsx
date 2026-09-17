"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function EveningRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/attendance");
  }, [router]);
  return <div className="page muted">Opening attendance…</div>;
}
