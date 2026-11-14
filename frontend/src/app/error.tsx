"use client";
import { useTopLoader } from "nextjs-toploader";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) {
  const loader = useTopLoader();
  useEffect(() => {
    loader.done(true);
  }, [loader]);
  return (
    <div className="empty-state" role="alert">
      <h2>We couldn&apos;t open this page</h2>
      <p>Your saved records are unchanged. Try loading the page again.</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
